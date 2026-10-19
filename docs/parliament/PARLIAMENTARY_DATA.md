# Parliamentary Data Model

Reference for how the parliament bot's data is structured and what is available for each
data type. **The parliament bot is Scotland-only (Scottish Parliament / Holyrood,
`RESEARCH_MODE=parliamentary_records`).** UK Parliament (Westminster) material is the separate
Westminster bot's (`westminster_records`), which uses the live Hansard, Members and Bills APIs and
keeps no local corpus; it is not covered here.

The bot draws on textual sources with different structures, freshness models and levels of
retrievable detail. The single most important distinction:

> **Committee transcripts *and plenary (chamber) debates* are crawled into local databases
> and are fully searchable and retrievable. Written answers, bills, and members are fetched
> live at query time and are excerpt-only / metadata-only.**

A further source — **Scottish Parliament TV video** — is not searched for content; it is an
*enrichment layer* that turns a plenary or committee citation into a timestamped video deep link
(the moment the words were spoken). It is built and switched off by default; see §8.

---

## 1. The Scottish Parliament session model

Holyrood organises its work into **parliamentary sessions** — the period between two
general elections. Each session contains all the meetings, debates, bills, and members
current during that term. The bot knows sessions as these `meeting_date` windows
(`SP_SESSIONS` in `server_py/src/agent/tools/parliament.py`), which the Session filter enforces:

| Session | Window (`meeting_date`) | In the local DB |
|---|---|---|
| Session 1 | 6 May 1999 – 6 May 2003 | Only if an admin refresh has ingested it (see §3) |
| Session 2 | 7 May 2003 – 2 May 2007 | As above |
| Session 3 | 3 May 2007 – 4 May 2011 | As above |
| Session 4 | 5 May 2011 – 4 May 2016 | As above |
| Session 5 | 5 May 2016 – 5 May 2021 | As above |
| **Session 6** | 6 May 2021 – 5 May 2026 | **Crawled automatically**, from its first meeting on 13 May 2021 |
| **Session 7** | 6 May 2026 – *open* | **Crawled automatically** |

### How sessions gate the source data

The SP Official Report search (`search-what-was-said-in-parliament`) **defaults to the
current session** and silently ignores a custom `dtDateFrom`/`dtDateTo` range that falls
outside it. To retrieve older sessions the request **must include `dateSelect=custom`** —
without it, a 2022 date window returns zero meetings even though the data exists. The crawler
sets this param on every listing request (`_fetch_window_meetings`, `backfill_sessions()` and
`backfill_plenary()` in `server_py/src/services/parliament_crawler.py`).

The automatic crawl starts at **`_BACKFILL_START` (13 May 2021, Session 6's first meeting)**,
covering Session 6 and Session 7. The dissolution gap between sessions simply returns empty
windows. Earlier sessions can be ingested on demand with the admin refresh (§3), or for every
start-up backfill by moving `_BACKFILL_START` further back.

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
| `meeting_id` | str | Meeting identifier from the Official Report (`?meeting=ID`). Lookups use the unique constraint below, whose leading column it is |
| `slug` | str | URL slug — committee code + date, e.g. `SPPAC-10-02-2022` |
| `iob_id` | str | Agenda item ("item of business") ID (`&iob=ID`) |
| `committee_code` | str, indexed | Short code, e.g. `SPPAC`, `FPA`, `PSRC` |
| `committee_name` | str, indexed | Full committee name |
| `meeting_date` | date, indexed | Date of the sitting |
| `agenda_item_title` | str | Title of the agenda item |
| `url` | str, unique | Canonical transcript URL (`slug?meeting=ID&iob=ID`) |
| `speeches` | JSONB | Ordered list of `{speaker, text}` objects |
| `full_text` | text | Committee name + agenda title + every speech as `speaker: text`, flattened for FTS |
| `fetched_at` | datetime | When the crawler stored the row |

- **Unique constraint** on `(meeting_id, iob_id)` — the crawler inserts with
  `ON CONFLICT DO NOTHING`, so re-crawls are idempotent and resumable.
- **Full-text search** runs `to_tsvector('english', coalesce(full_text,'')) @@ plainto_tsquery(...)`
  (GIN-indexed on that expression), ranked by `ts_rank`, optionally filtered by committee
  (committee table only, ILIKE on name/code) and date range.
- **OR-fallback** — `plainto_tsquery` ANDs every term, so one truly-absent query term (e.g.
  "unhoused" when the corpus says "homeless") returns **0 rows**. When the exact search returns
  zero rows, both `_search_*_db` re-run the *same* query (same filters, same `ts_rank`) with an
  OR-combined `to_tsquery` (`_or_tsquery` builds it: lowercase, tokenise, drop short/stopword
  tokens, join with ` | `), and if that finds anything they add
  `note: "No exact (all-terms) match; broadened to any-term search."`. Fires **only** on zero
  rows — precision on the queries that already match is untouched. An empty/stopword-only token
  set skips the fallback.

### How the crawler populates them

`server_py/src/services/parliament_crawler.py`, started on app startup **only when
`RESEARCH_MODE=parliamentary_records`**:

1. **`backfill_sessions()`** — one-shot at startup (committee). Requests the Official Report
   listing with `showCommittee=true&dateSelect=custom&dtDateFrom=X&dtDateTo=Y` in two-week
   windows, and takes only meetings with no stored rows. For each it fetches the meeting page
   (→ committee name + agenda items) and then each agenda item's transcript page, parsed with
   **`_parse_sp_plenary_transcript`** (committee and plenary pages share the same
   `<p id="orscontributions_...">` markup; the speaker is the first `/msps/` link). **Start point
   is adaptive (`_backfill_window_start`):** on an empty table it walks from `_BACKFILL_START`
   (13 May 2021); on a populated table it starts 14 days before the newest stored meeting, so a
   normal restart re-scans only recent windows instead of re-walking five years. Items with no
   parseable speeches (not yet published) are skipped, not stored, so the daily delta retries
   them. A 1.5-second pause separates requests.
2. **`backfill_plenary()`** — one-shot (plenary). Same as above but with `showPlenary=true`
   and `_parse_sp_plenary_meetings` (which *includes* the `meeting-of-parliament-*` slugs the
   committee parser excludes). Uses the same adaptive start. Runs **after** `backfill_sessions()`
   so the two don't hit the origin concurrently. Transcript fetches use
   `_fetch_sp_page_with_retry` (4 attempts with backoff, rejects responses under 20 KB, falls
   back to UTF-8) because the large plenary pages intermittently return a Cloudflare 524 error
   page.
3. **`backfill_captions()`** / **`backfill_committee_captions()`** — run after the plenary
   backfill and cache SP TV captions for crawled meetings that have none yet (§8). No-ops unless
   `ENABLE_VIDEO_DEEPLINKS` is on.
4. **`background_crawl_loop()`** / **`background_plenary_crawl_loop()`** — run
   `crawl_sp_new_meetings()` / `crawl_sp_new_plenary()` daily as a **trailing-window delta**:
   they re-scan the last `_DELTA_WINDOW_DAYS` (30) and *reprocess* every meeting in that window,
   not just brand-new `meeting_id`s. This is how new sittings **and** late-published transcripts
   / newly-added agenda items on already-seen meetings are picked up — the source sends no
   `Last-Modified`/`ETag` (Cloudflare `no-cache, no-store`), so a recency-window re-scan against
   our stored state is the only way to detect updates. Per-item `(meeting_id, iob_id)` existence
   checks keep completed transcripts from being re-fetched, so steady-state cost is ~one
   meeting-page GET per recent meeting per day (1.2 seconds between requests). The committee
   loop's first run is at startup; the plenary loop's is ~5 minutes later, so the two don't
   overlap. With video deep links on, a meeting that gains new items also has its captions
   cached.
5. **Manual refresh** — Admin Portal → Developer → Operations → **Parliamentary Data Refresh**
   (shown on the parliament bot only) re-crawls one session, 1 to 7, or "All sessions" (Session 6
   start to today). It reprocesses every meeting in the session's window, committee then plenary,
   then fills any missing captions. It runs in the background, one at a time, and the panel shows
   how many items it stored. Sessions 1–5 are not crawled automatically, so a refresh there is a
   first ingest.

Written answers, bills, and members are **not** crawled — they are fetched live per query.

### Checking coverage

Admin Portal → **Data Coverage** (shown to the `admin` account; `GET /api/stats/parliament-coverage`)
reports what the crawler holds, from the bot's own database:

- per data type (committee transcripts, plenary debates): meetings, agenda items, items with and
  without text, distinct committees (committee only), and the earliest and latest meeting date;
- SP TV video captions: events cached, usable caption tracks, events without one, YouTube-hosted
  events, and how many plenary and committee meetings have a video event;
- a per-session table of meetings, items and video events.

Its session selector offers Session 6 (counted from 13 May 2021), Session 7 and "All sessions";
anything an admin refresh has ingested from Sessions 1–5 appears under "All sessions" only. On a
bot that is not the parliament bot every figure is zero.

---

## 4. Data types and what is available

| Data type | Source | Tool(s) | Keyword search | Full text retrievable | Date filter | Session coverage |
|---|---|---|---|---|---|---|
| **Committee transcripts** | Local DB `sp_committee_items` (crawled from SP Official Report) | `search_scottish_committee_transcripts` → `get_scottish_committee_transcript` | ✅ FTS | ✅ verbatim speeches | ✅ | Session 6 + 7 (plus any session an admin has refreshed) |
| **Plenary (chamber) debates** | Local DB `sp_plenary_items` (crawled from SP Official Report) | `search_scottish_plenary` → `get_scottish_plenary_debate` | ✅ FTS | ✅ **verbatim speeches** | ✅ | Session 6 + 7 (plus any session an admin has refreshed) |
| **Plenary debates (fallback)** | TheyWorkForYou `getHansard` (live) | `search_scottish_parliament` | ✅ | ❌ excerpt only | ⚠️ ignored by TWFY | Whatever TWFY indexes (older/breadth fallback) |
| **Written answers** | TheyWorkForYou `getHansard` type=spwrans (live) | `search_scottish_parliament` (`debate_type=written_answers`) | ✅ | ❌ excerpt only | ⚠️ ignored | Whatever TWFY indexes |
| **Bills** | `data.parliament.scot/api/bills` (live) | `search_bills` | ⚠️ client-side keyword filter | n/a (metadata) | ❌ | All Holyrood bills |
| **Members (MSPs)** | TheyWorkForYou `getMSPs` (live) | `get_member_info` | by name | n/a (member record) | ❌ | Whatever `getMSPs` returns for the name |
| **Video timestamps** *(built, off by default)* | Scottish Parliament TV (Vualto) — playback model + HLS WebVTT captions; `sp_video_captions` cache | *(enrichment on plenary **and committee** citations, no tool)* | n/a (not searched) | n/a (produces a deep link, not text) | n/a | Plenary + committee meetings in the DB where captions exist (gated on `ENABLE_VIDEO_DEEPLINKS`) |

### Committee transcripts & plenary debates — the fully-retrievable sources

- **Committee search** (`search_scottish_committee_transcripts`): full-text keyword search
  over the DB. Returns up to 10 ranked agenda items with `meeting_id`, `slug`, `iob_id`,
  `committee_name`, `meeting_date`, `agenda_item_title`, `url`, and a 300-char excerpt.
  Optional `committee` and `date_from`/`date_to` filters.
- **Committee retrieve** (`get_scottish_committee_transcript`): pass `meeting_id` + `slug` +
  `iob_id` back to fetch the verbatim transcript — full speeches (minister responses, member
  questions, witness evidence). This is a **live fetch** of the transcript page (not the DB),
  scoped to the agenda item by its stored title and returning
  `{page_title, url, speeches[], total_speeches}`.
- **Plenary search** (`search_scottish_plenary`): full-text keyword search over
  `sp_plenary_items`. Same result shape as committee search without `committee_name`, and no
  `committee` filter. Optional `date_from`/`date_to`.
- **Plenary retrieve** (`get_scottish_plenary_debate`): pass `meeting_id` + `slug` + `iob_id`
  back to fetch the verbatim chamber speeches for that agenda item (a ministerial statement,
  an FMQs exchange, a named debate). Live fetch parsed by `_parse_sp_plenary_transcript`
  (scoped to the item via its stored `agenda_item_title`), with retry/backoff for Cloudflare
  524s. Returns `{page_title, url, speeches[], total_speeches}`. This is the *Pepper v Hart*
  route — the minister's exact words, verbatim.
- Both retrieval tools return at most **150 speeches** (`_cap_speeches`): beyond that the
  result carries `truncated: true` and a note telling the model to retrieve a narrower agenda
  item, while `total_speeches` keeps the true count. With video deep links on, matched speeches
  carry a `video_deeplink` (§8).
- If a DB is empty (crawl not yet finished), the corresponding search returns a graceful note
  telling the model to fall back to `search_scottish_parliament`.

### Plenary (fallback) & written answers — excerpt only

- Backed by TheyWorkForYou's `getHansard`. `search_scottish_parliament` is **excerpt-only**
  (max 400 chars each, up to 10 results) — for full plenary text use `search_scottish_plenary`
  + `get_scottish_plenary_debate` instead. `search_scottish_parliament` remains useful as an
  older-session / breadth fallback (TWFY may index dates not yet crawled into `sp_plenary_items`)
  and is the route for **written answers**.
- TWFY quirks baked into the code:
  - `type=sp` is **broken** (returns Westminster content) — the caller omits it and
    post-filters results to SP by `/sp/` and `/spwrans/` listurl patterns. Written answers use
    `type=spwrans`, which works.
  - Debate titles come from `speech.parent.body` (HTML), not `speech.debate` (always empty).
  - `date_from`/`date_to` are **not supported** by TWFY `getHansard` and are silently ignored.
- Requires `TWFY_API_KEY`; without it `search_scottish_parliament` returns a clear error.

### Bills — metadata only

- The Scottish Parliament Bills API returns the full list; there is no server-side search,
  so `search_bills` fetches everything and keeps the bills whose short or long title contains
  the query (case-insensitive), up to 10. Returns `billId`, `shortTitle`, `currentStage`, and a
  link — no bill text.

### Members (MSPs) — member record

- `get_member_info` calls TWFY `getMSPs` with a name search (the old `getMSPInfo` endpoint
  was removed) and returns TWFY's matching records unchanged. Scotland/MSPs only. Uses
  `TWFY_API_KEY`.

---

## 5. Filter enforcement

The frontend exposes a **Record type** filter (Chamber debates `debates` / Written answers
`written_answers` / Committee transcripts `committee`), a **Session** filter (multiselect of
Sessions 1–7, defaulting to the latest) and a **Date range**. `_apply_parliament_filters` in
`parliament.py` maps these onto tools, filling in an argument only where the model left it out:

- `debates` → redirects `search_scottish_parliament` to `search_scottish_plenary` (the
  full-text plenary route); a `search_scottish_plenary` call is allowed through.
- `written_answers` → sets `debate_type='written_answers'` on `search_scottish_parliament`.
- `committee` → short-circuits `search_scottish_parliament` **and** `search_scottish_plenary`
  with a redirect telling the model to use `search_scottish_committee_transcripts`.
- Sessions → collapsed to one window from the earliest selected start to the latest selected
  end (open-ended if Session 7 is included) using `SP_SESSIONS`, then intersected with any date
  range, the tighter bound winning. A non-contiguous selection (e.g. Session 1 + 7) broadens to
  the enclosing span.
- The resulting dates → merged into `search_scottish_committee_transcripts` and
  `search_scottish_plenary` (honoured, DB queries) and `search_scottish_parliament` (accepted but
  ignored downstream by TWFY).

A `search_budget` of 3 caps the total number of `search_scottish_plenary` +
`search_scottish_parliament` + `search_scottish_committee_transcripts` calls per Worker run.
A search beyond it returns a stop instruction (retrieve from the results already found, or
report that nothing was found) instead of results, and is counted in `search_budget_blocked`
on the Efficiency tab. This forces weaker models to stop searching and synthesise.

---

## 6. Known gaps — data a researcher may expect but the bot does not (yet) provide

Prioritised by impact for the bot's audience (legal professionals doing statutory-interpretation and
scrutiny research). None of these are bugs — they are coverage boundaries.

### Tier 1 — undercuts the core legal use case

- **Bills are metadata-only.** `search_bills` returns title, current stage, and a link.
  Missing the material legal professionals reason from: bill text, how a provision changed
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

- **Committees & plenary: Session 6–7 by default.** Pre-May-2021 work returns nothing from the
  crawled DBs unless an admin has refreshed that session (§3). The TWFY
  `search_scottish_parliament` fallback may reach further back but remains excerpt-only.
- **Plenary date filtering** — honoured for `search_scottish_plenary` (DB query). It is still
  silently ignored by the TWFY `search_scottish_parliament` fallback (`getHansard` drops
  `date_from`/`date_to`).
- **Transcript truncation** — `_parse_sp_plenary_transcript` cuts each speech at 3,000
  characters, and the crawler uses the same parser, so the stored `full_text` (and therefore
  search) holds the same cut text. The retrieval tools also return at most 150 speeches per
  agenda item (§4).
- **MSP data is the member record only** — no Register of Interests, no per-member voting history.

---

## 7. Quick reference — external endpoints

| Source | Base URL | Auth |
|---|---|---|
| SP Official Report (committee + plenary crawl + transcript fetch) | `https://www.parliament.scot/chamber-and-committees/official-report/search-what-was-said-in-parliament` | none |
| TheyWorkForYou (`getHansard`, `getMSPs`) | `https://www.theyworkforyou.com/api` | `TWFY_API_KEY` |
| SP Bills | `https://data.parliament.scot/api/bills` | none |
| SP TV meeting page, archive + playback model *(video, off by default)* | `https://www.scottishparliament.tv/meeting/{slug}`, `/archive?DateFrom=…&DateTo=…`, `/Player/PlaybackModel/{eventId}` | none |
| SP TV video/caption CDN *(video, off by default)* | `https://scotparl-live.cdn.vustreams.com/…` (HLS `.m3u8` + WebVTT segments) | none |

> The two SP TV hosts need to be reachable from the (internet-restricted) target only when
> `ENABLE_VIDEO_DEEPLINKS` is on. If they are unreachable, resolution fails soft: no link is
> attached and the Official Report citation stands.

---

## 8. Scottish Parliament TV — video timestamp deep links

**Status:** built for plenary **and committee** meetings, and **off unless `ENABLE_VIDEO_DEEPLINKS`
is set** (default off; for the parliament bot it goes in `bots/parliament/.env`). Build briefs:
[`VIDEO_DEEPLINK_PLAN.md`](VIDEO_DEEPLINK_PLAN.md) (plenary) and
[`VIDEO_COMMITTEE_SPIKE.md`](VIDEO_COMMITTEE_SPIKE.md) (committee). Implemented in
`services/sptv_client.py` (resolve — `resolve_event` for plenary, `resolve_committee_event` for
committee — + captions), `services/caption_match.py` (text→time match),
`parliament_crawler.backfill_captions()` / `backfill_committee_captions()` (caching), and
`SpVideoCaption` / `sp_video_captions`. When enabled, `get_scottish_plenary_debate` **and
`get_scottish_committee_transcript`** attach a `video_deeplink` to matched speeches. This section
documents the *data source* — how SP TV video maps to our Official Report data.

### What it adds
When the bot cites a plenary speech, it can also link to the **exact moment** in the SP TV video where
the words were spoken — e.g. *"the Cabinet Secretary said X — watch from 15:02:46"*. This is an
enrichment on an existing citation, not a new search capability: video is never searched for content,
and if a link can't be resolved the normal Official Report citation stands.

### How the mapping works (the data chain)
SP TV runs the **Vualto** player. There is no field linking an Official Report speech to a video time,
so the link is *derived* through captions:

1. **Meeting → event.** Plenary SP TV slug is derivable from the meeting date
   (`meeting-of-the-parliament-{month}-{day}-{year}`, which differs from the Official Report slug).
   The meeting page HTML embeds the Vualto `eventId` GUID.
2. **Event → streams.** `GET /Player/PlaybackModel/{eventId}` returns JSON (no auth): `eventTitle`,
   `eventDescription` (the agenda), `startTime` (broadcast start), `hlsStreamUrl`, `isYoutube` /
   `youtubeUrl`.
3. **Streams → captions.** The HLS master playlist carries a WebVTT subtitle track. The caption
   playlist has one `#EXT-X-PROGRAM-DATE-TIME` anchor (matches `startTime`) plus 6-second WebVTT
   segments (thousands per sitting).
4. **Caption text → time.** Match a distinctive phrase from the speech text against the cached
   caption transcript; the wall-clock time is anchor + segment offset + cue offset.
5. **Time → link.** The player accepts `?clip_start=HH:MM:SS&clip_end=HH:MM:SS` where the times are
   **local wall-clock (Europe/London)**. The clip runs 60 seconds. Final link:
   `https://www.scottishparliament.tv/meeting/{slug}?clip_start=…&clip_end=…`.

### Two hard-won implementation facts
- **Caption timing = segment ordinal × 6s (`EXTINF`), using the TRUE HLS playlist index.** The
  per-segment MPEGTS counter resets mid-stream, so global MPEGTS deltas produce garbage (negative)
  offsets — only the single PROGRAM-DATE-TIME value anchors the timeline. Cue timestamps inside each
  segment restart near zero, so a cue's offset is `segment_index × 6 + cue_start`. **The ordinal must be
  each segment's real index in the HLS playlist, not the count of caption-bearing segments:** ~7% of
  segments carry no captions (171 of 2317 in the validation sitting), so counting only those
  undercounts and puts speeches minutes too early. `sptv_client.fetch_caption_transcript` uses
  `seg_index` over the full playlist. Validated on the 2 June 2026 "Phone-free Classrooms" statement:
  `15:02:46`, against the Official Report's own embedded `15:02` marker.
- **Match on the rarest phrase, within the agenda-item window.** Boilerplate openings ("I thank the
  cabinet secretary…") recur throughout a sitting and cause false matches to earlier occurrences.
  Prefer the caption phrase with the fewest occurrences and constrain the search to at/after the
  agenda item's first distinctive speech. `clip_start` is real Europe/London wall-clock (DST-correct
  via `zoneinfo`).

### Coverage & limitations
- **Plenary and committee both supported.** Plenary slug derives from the date; committees
  can't (several meet the same day), so committee events are resolved via the **SP TV archive
  date-filter** (`GET /archive?DateFrom=DD/MM/YYYY&DateTo=…`), which lists every event that day with
  the committee name in the link text — matched on `committee_name` to disambiguate, then the meeting
  page yields the eventId (`sptv_client.resolve_committee_event`). Everything downstream of `eventId`
  (playback model, HLS captions, matcher) is identical to plenary. Captions are cached one row per
  event in `sp_video_captions`, keyed to meetings by `meeting_id`.
- **Caption coverage (measured on the full Session 6+7 backfill, July 2026).** ~1,140 SP TV events
  cached in `sp_video_captions`; **~540 (~47%) have a usable caption track** (`caption_ok=true`) and
  can yield a video link. The remainder have no subtitle track (`caption_ok=false`) — no link,
  fail-soft. Availability skews strongly to recent sittings: most June-2026 plenary and committee
  events are captioned, while many pre-2024 events are not. A `caption_ok=false` row is still stored
  so the event isn't retried. The Data Coverage tab (§3) shows the current figures.
- **Accuracy ±a few seconds.** Live captions are lightly garbled/rolling; distinctive 8–12 word
  windows match cleanly, but very short or heavily paraphrased contributions fall back to the page
  link.
- **YouTube-hosted events get no link.** Some events are served via `youtubeUrl` instead of HLS.
  There is no HLS caption track to read, so they are stored with `caption_ok=false` and never
  matched (`caption_match` can build a YouTube `&t=` link, but no YouTube event reaches it).
- **Undocumented contract.** `clip_start`, `/Player/PlaybackModel/`, and the HLS layout are unofficial
  and could change without notice; all parsing fails soft (omits the link, never errors a response).
