# Westminster (UK Parliament) video deep links — implementation plan

**Status:** DRAFT (not authorised to build). Scoped 2026-07-25, off the back of the
read-only feasibility spike (`docs/parliament/WESTMINSTER_VIDEO_SPIKE_PLAN.md`, verdict
**GO cheap, ~2–3 days for the video layer only**).
**Tracked as:** TODO.md → D11.
**Companion pattern:** the Scotland equivalent — `docs/parliament/VIDEO_DEEPLINK_PLAN.md`,
`server_py/src/services/sptv_client.py`, `caption_match.py`. This plan deliberately
mirrors that structure so the two are easy to compare.

---

## 0. Prerequisite — READ FIRST (this feature cannot ship standalone)

The parliament bot is **Scotland-only today**. Westminster was removed on purpose:
`search_hansard` / `get_hansard_debate` deleted, `get_member_info` / `search_bills`
narrowed to Holyrood, `_slim_hansard_results` post-filters TWFY to `/sp/` listurls only.

**Video links are the last ~10% on top of re-introducing Westminster as a supported
jurisdiction** (Hansard retrieval tools, search/crawl layer, filter/session plumbing,
prompt scope — a ~Scotland-sized effort). That re-introduction is a **separate product
decision** (D11) that has *not* been made, and the reason for the original removal must
be understood before it is.

**Therefore this plan assumes a re-introduced Westminster Hansard retrieval layer exists**
(specifically: a tool that returns a Hansard debate with its `Date`, `House`, and
per-contribution `AttributedTo` / `MemberId` / `Timecode`). Everything below is the
enrichment layer that hangs off that. If the Westminster-scope decision is *no*, none of
this is built. The plan is written now purely so the video piece is costed and de-risked
for that conversation.

The two phases are independently sequenced: **Phase W0** (Westminster re-introduction) is
out of scope here and is its own plan; **Phases 1–5** below are the video layer and are
what the 2–3 day estimate covers.

### 0.1 Filtering & jurisdiction UI — a **Phase W0** concern, NOT the video layer

**Direct answer to "what about filtering?": the video layer needs no filter changes.**
Video links derive their `House` + `date` from each returned Hansard debate record (which
carries both), *not* from filter state — so they attach correctly regardless of whether or
how the user has set filters. There is **no filter→video dependency**. Any Commons/Lords
filter merely narrows what's retrieved, which incidentally narrows which citations get a
link — emergent, not a coupling.

**But Westminster filtering is real W0 work, and it is *not* "reuse Scotland's filters".**
The current parliament-bot filter stack is Holyrood-shaped end-to-end:
- `client/src/constants/research.js` — `RECORD_TYPE_OPTIONS`
  (`debates`/`written_answers`/`committee`), `SESSION_OPTIONS` (Holyrood Sessions 1–7),
  `LATEST_SESSION = 7`.
- `client/src/hooks/useFilters.js` — state (`recordType`, `sessions`, `dateFrom/To`, …),
  global `filter_*` + per-chat `filter_chat_{id}` localStorage snapshots.
- `client/src/components/ResearchFiltersModal.jsx` + the fixed pills header bar
  (draft-and-apply modal, commit `6d3dbea`).
- Backend `_apply_parliament_filters` + `SP_SESSIONS` (Holyrood session→meeting-date
  windows) in `agent/tools/parliament.py`; carried on the request as `_pt_sessions` etc.

What Westminster changes, dimension by dimension:

1. **New `House` dimension (Commons / Lords / both).** Holyrood is *unicameral*, so this
   filter does not exist today. It is the one genuinely new control: a `HOUSE_OPTIONS`
   constant, a `house` state in `useFilters`, a pill + modal control, and a backend
   mapping onto the Hansard `house` param **and** parliamentlive `/Search?House=`. (This is
   also the dimension the video-GUID lookup keys on — but, per above, the video layer reads
   it from the debate record, so it works even if the *filter* is never built.)
2. **Different record-type taxonomy.** Westminster is not debates/written_answers/committee.
   The Hansard API's own `overview/sectionsforday` returns the real taxonomy — the spike
   saw `["Debate","WestHall","WMS","Correction","PBC"]` (Chamber debate, Westminster Hall,
   Written Ministerial Statements, Corrections, Public Bill Committee), plus Written Answers
   and Select-Committee oral evidence. `RECORD_TYPE_OPTIONS` must be replaced/branched and
   mapped onto those section types, not the Scottish ones.
3. **Different session model.** Holyrood Sessions 1–7 (fixed 4–5yr terms) → Westminster
   **Parliaments and sessions within them** (a Parliament per general election, sessions
   ~annually, e.g. 2024– Parliament / 2024–25 session). Needs its own options list and a
   Westminster `*_SESSIONS` date-window map analogous to `SP_SESSIONS`.
4. **Date range** — the one piece that ports cleanly (same `dateFrom/To` plumbing; Hansard
   is date-queryable directly).

**Coexistence architecture decision (W0, flag for the product call):** either (a) add
Westminster to the *same* parliament bot, in which case the filter controls become
**jurisdiction-conditional** (show House + Westminster record types + Westminster sessions
when Westminster is in scope; Holyrood set otherwise) — more UI state, one bot; or (b) run
Westminster as a **separate federated bot** (like the current legislation/parliament split)
with its own filter constant set and no conditionality — cleaner separation, more infra.
This is a W0 decision, not a video-layer one, but it sizes the filtering UI work and so
belongs in the same product conversation. **None of it gates or is gated by the video
links.**

---

## 1. What we're building & why

Given a Westminster spoken contribution retrieved from Hansard, emit a deep link that
opens the parliamentlive.tv video **at that moment**:
`https://parliamentlive.tv/event/index/{GUID}?in=HH:MM:SS` (optionally `&out=HH:MM:SS`).

**Why it's dramatically cheaper than Scotland:** SP TV exposes *no* speech→time field, so
Scotland derives timing from HLS WebVTT captions (segment-ordinal×6s, rarest-phrase
matching, DST wall-clock) and only reaches ~47% coverage. **Westminster publishes
per-agenda-item wall-clock timecodes natively, on the same timeline in both Hansard and
parliamentlive.** The entire caption-derivation layer is **deleted**, not ported. Coverage
is effectively complete for archived events.

---

## 2. Feasibility — proven by the spike (2026-07-25)

All verified against live endpoints, no auth, server-usable (see spike §6 for trimmed
real samples). The four external facts we rely on:

1. **Timecode index (Q1):** `GET https://www.parliamentlive.tv/Event/Logs/{GUID}` →
   HTML fragment, no auth/cookie. Each `<li class="logouter">` pairs a
   `<span class="time-code" data-time="2026-07-16T08:33:41Z">` (**UTC**) + visible BST
   render (`09:33:41`) with the agenda item / speaker (name, role, constituency, party).
   *(Dead-end: `data.parliamentlive.tv/api/event/{GUID}` → 401; not used.)*
2. **Date+House → event GUID (Q2a):** `GET https://www.parliamentlive.tv/Search?House=Commons&Start=DD/MM/YYYY&End=DD/MM/YYYY`
   → results page listing that day's events as `Event/Index/{GUID}` links. One **Chamber**
   event per House per day ⇒ unambiguous for chamber debates; committees disambiguate by
   name (same pattern as SP's `resolve_committee_event`).
3. **Hansard timecodes (Q2b):** `hansard-api.parliament.uk` debate JSON carries a
   section-level **`Timecode`** on the **same wall-clock** as parliamentlive
   (Hansard local `09:45:39` == parliamentlive `08:45:39Z`). No event GUID in Hansard.
4. **Deep-link format (Q3):** `parliamentlive.tv/event/index/{GUID}?in=HH:MM:SS[&out=HH:MM:SS]`
   (local wall-clock), confirmed via the site's own `GetShareVideo` share-link generator.

**The one engineering nuance to honour:** Hansard's `Timecode` is populated at
**section / agenda-item** granularity, not on every `Contribution` (spike sample: 66
populated vs 200 null). For agenda-item-level links that's enough on its own. For
**per-speech** precision, match the Hansard contribution to the `/Event/Logs` index entry
by **speaker + order**, then use that entry's `data-time`. Both sources share wall-clock,
so a coarse time bound makes the match robust. No captions, no fuzzy text matching.

---

## 3. Architecture decisions (proposed — confirm before building)

- **`in=` value comes from a wall-clock time, computed once.** Preferred source order per
  contribution: (a) the matched `/Event/Logs` entry's `data-time` (UTC → convert to
  Europe/London local `HH:MM:SS`); (b) fall back to the Hansard section `Timecode`
  (already local — use its `HH:MM:SS` directly). Reuse the `zoneinfo`-based DST-correct
  conversion pattern from `caption_match.py` (never a hard-coded +1h).
- **No caption pipeline, no HLS, no offset index, no crawler.** The Logs index is fetched
  on demand and cached per event. There is **no** background crawl analogous to
  `parliament_crawler.backfill_captions()` — Westminster has no equivalent need because
  the timecodes are served directly and cheaply.
- **Cache the parsed Logs index per event GUID**, not per contribution — one small row per
  event (`plive_events`), fetched lazily the first time any contribution from that event
  is cited, then reused. Analogous to `sp_video_captions` but storing a plain agenda index
  instead of a caption transcript + offset index.
- **Fail-soft, additive, dark-launched.** Any resolution/parse failure just omits the
  link (identical philosophy to SP TV). Gated behind a feature flag so it's off until the
  Westminster scope decision lands.
- **Emit the watch-page deep link only** (`parliamentlive.tv/event/index/{GUID}?in=…`),
  never the embed iframe (`videoplayback.parliamentlive.tv`, intermittently suspended).
- **The server never fetches `parliamentlive.tv` (bare host)** — that URL is only handed
  to the user's browser. Server-side fetches are `www.parliamentlive.tv` +
  `hansard-api.parliament.uk`.

---

## 4. Data model

New table `plive_events` (SQLAlchemy model `PliveEvent` in `models.py`), one row per
parliamentlive event:

| column | type | notes |
|---|---|---|
| `id` | int PK | |
| `event_id` | str(64), unique | parliamentlive event GUID |
| `house` | str(16) | `Commons` / `Lords` |
| `event_date` | Date, index | sitting date |
| `business` | str(64) | `Chamber` / `Westminster Hall` / committee name |
| `agenda_index` | JSONB | `[{utc: "…Z", local_hms: "09:33:41", title, speaker, order}, …]` parsed from `/Event/Logs` |
| `resolve_ok` | bool | false if GUID/Logs couldn't be resolved (negative cache) |
| `fetched_at` | DateTime | for staleness / re-fetch if ever needed |

Additive `ALTER TABLE … ADD COLUMN IF NOT EXISTS` on startup (same convention as the
cache/efficiency columns). No backfill.

---

## 5. Phased implementation (video layer — the 2–3 day estimate)

### Phase 1 — parliamentlive client (`server_py/src/services/plive_client.py`) — ~1 day
Mirrors `sptv_client.py`'s shape (async `httpx`, `_get` with retries, fail-soft), minus
all caption code.
- `resolve_event(client, house, event_date, business=None) -> Optional[tuple[str, str]]`
  — GET `/Search?House={house}&Start=DD/MM/YYYY&End=DD/MM/YYYY`, parse `Event/Index/{GUID}`
  links + their titles, pick by `business`/title (Chamber default). Committee variant
  matches on committee name (port `_norm_committee_name`).
- `fetch_agenda_index(client, event_id) -> Optional[list[dict]]` — GET `/Event/Logs/{GUID}`,
  parse each `<li class="logouter">` into `{utc, local_hms, title, speaker, order}`.
  Regexes: `data-time="([^"]+)"`, the visible `time-code` text, and the `<h4>` agenda/
  speaker text. (Structured HTML fragment — straightforward `re` parsing, as with the SP
  HTML parsers.)
- Dataclasses `PliveEvent` / `AgendaEntry` for internal use.

### Phase 2 — event cache accessor (`plive_client.py` + `models.py`) — folded into Phase 1
- `get_or_build_event(session, client, house, event_date, business)` — lookup
  `plive_events` by `(house, event_date, business)`; on miss, `resolve_event` +
  `fetch_agenda_index`, store (incl. negative `resolve_ok=False` cache), return the row.
  Lazy, no crawler.

### Phase 3 — matcher (`server_py/src/services/plive_match.py`) — ~0.5 day
- `deeplink_for_contribution(agenda_index, contribution) -> Optional[dict]` — match a
  Hansard contribution to an agenda entry by **speaker + order** (normalise names like
  `_party_tokens` does for case law); on match, build
  `event/index/{GUID}?in={local_hms}` (+ `&out=` from the next entry's time if available).
  Fallback: if no Logs match, use the contribution's own Hansard section `Timecode`
  (local) directly. Return `{video_deeplink, in, out}` or `None`. Fail-soft.
- `annotate_contributions(agenda_index, contributions) -> int` — mutate the list adding
  `video_deeplink`, returning count annotated (mirrors `caption_match.annotate_speeches`).

### Phase 4 — wire into the (re-introduced) Westminster retrieval tool — ~0.5–1 day
In the Westminster `get_hansard_debate` tool (Phase W0), after parsing the debate and
**only when `settings.enable_westminster_video_deeplinks`**:
- derive `house` + `event_date` from the debate; `get_or_build_event(...)`;
- `annotate_contributions(row.agenda_index, contributions)` (sets `video_deeplink` on each
  contribution, shape `{url, clip_start, provider: "westminster"}`);
- append a Phase-2-style nudge noting links are attached.
This mirrors the two attach sites in `parliament.py` (~L832/L890) for the SP tools.

### Phase 4b — UI / frontend changes — ~0.5 day
The video link surfaces in **two** places today, both currently **hard-coded to
Scotland**. Westminster reuses the same plumbing; the only real change is making the
provider label dynamic. Keep changes minimal and match the surrounding code style.

1. **Sources-rail "Watch" link** (`client/src/components/SourcesRail.jsx` ~L470–488).
   Today it renders `▶ Watch {clip_start}` with a hard-coded title
   *"Watch on Scottish Parliament TV"* whenever `s.video?.url` exists. The `s.video`
   object shape (`{url, clip_start}`) is provider-agnostic and works as-is for
   Westminster — **the only fix is the label/hover text**:
   - Backend: extend the video object emitted in `agent_shared.py` (the two SP branches at
     ~L230/L278, plus the **new Westminster `get_hansard_debate` branch**) to carry a
     `provider` (`"sp"` / `"westminster"`) and/or a ready `label`
     (`"Scottish Parliament TV"` / `"UK Parliament TV"`).
   - Frontend: replace the hard-coded string with `s.video.label` (fallback to the current
     SP text so existing rows are unchanged). e.g.
     `title={\`Watch on ${s.video.label ?? 'Scottish Parliament TV'}${s.video.clip_start ? \` from ${s.video.clip_start}\` : ''}\`}`.
   - **Style:** keep the existing inline-style / `var(--accent)` convention already in that
     block (do **not** introduce Tailwind token classes here — match surrounding code).
     No new component, no layout change; the `▶ Watch HH:MM:SS` affordance is identical.
2. **Inline answer citation link** (prompt-driven, not a component). `prompts.py:607`
   instructs the model to append `— [▶ watch from CLIP_START](VIDEO_URL)` after a quote
   when a speech has a `video_deeplink`. The **Westminster worker system prompt** (Phase
   W0) needs the equivalent instruction, referencing `get_hansard_debate`'s
   `video_deeplink`/`clip_start`/`url` fields. This renders through the existing markdown
   pipeline — **no new UI code**, just a prompt line.

**No admin/config UI change.** Like the SP feature, this is dark-launched via the
`ENABLE_WESTMINSTER_VIDEO_DEEPLINKS` env flag only — there is no toggle in the Admin
Portal, so `AdminPortal.jsx` / Developer tab are untouched.

**No new jurisdiction/filter UI here.** Any Westminster House filter, record-type/session
options, filter pills, or modal controls belong to **Phase W0** — see §0.1, which sets out
why Westminster filtering is *not* a reuse of Scotland's (new House dimension, different
record taxonomy, different session model). The video layer reads `House`/`date` from the
Hansard debate record, so it is independent of whether any filter UI exists. This plan
touches only the citation "Watch" affordance.

**Build/deploy reminder:** frontend is pre-built and committed — after the `SourcesRail.jsx`
edit, `npm run build` in `client/` and force-add `client/dist/` in the same commit
(per CLAUDE.md deployment workflow).

### Phase 5 — config, tests, docs — ~0.5 day
- **Config:** `ENABLE_WESTMINSTER_VIDEO_DEEPLINKS` (default `false`) and
  `PLIVE_BASE_URL` (`https://www.parliamentlive.tv`) in `config.py` + `.env` table in
  CLAUDE.md. (Kept separate from `ENABLE_VIDEO_DEEPLINKS` so Scotland/Westminster toggle
  independently.)
- **Tests:** capture 1–2 fixtures — a `/Event/Logs/{GUID}` fragment and a Hansard debate
  JSON — and unit-test `fetch_agenda_index` parsing + `deeplink_for_contribution` matching
  (incl. the speaker-flip / no-match fallback paths). Pattern: `tests/` alongside the SP
  caption tests.
- **Docs:** CLAUDE.md "SP TV video deep links" gets a Westminster sibling paragraph;
  External API Dependencies table gains `www.parliamentlive.tv` + `hansard-api.parliament.uk`;
  update TODO.md D11.

---

## 6. Reachability / whitelist (internet-restricted target)
Must be whitelisted server-side: **`www.parliamentlive.tv`** (Logs + Search),
**`hansard-api.parliament.uk`** (debate JSON — needed by Phase W0 regardless).
Optional: `data.parliamentlive.tv` (Atom feed; not used if `/Search` does GUID lookup).
Not server-side: `parliamentlive.tv` (emitted to users' browsers only),
`videoplayback.parliamentlive.tv` (embed only). Run `server_py/test_apis.ps1`-style checks
against the target before enabling the flag.

---

## 7. Open questions / risks (raise before starting)
- **Playback not browser-verified.** `?in=`/`&out=` confirmed via the site's own
  share-URL generator (authoritative), but no live player seek was driven. Low risk;
  verify with one manual browser check during Phase 5.
- **Sub-item precision.** Hansard `Timecode` is per-section; per-speech placement relies
  on the Logs speaker+order match. Acceptable for an MVP; the fallback is agenda-item-level.
- **Committee disambiguation** (several committees/day) — match on committee name, as SP does.
- **Historical GUID coverage** — verified for a recent sitting; archive depth via `/Search`
  date range not probed. Negative-cache misses so we don't re-hit dead lookups.
- **Lords vs Commons** — spike focused on Commons Chamber; confirm Lords events expose the
  same `/Event/Logs` shape (feed shows many Lords events, so expected — verify in Phase 1).
- **HTML-fragment fragility** — `/Event/Logs` is HTML, not JSON, so markup changes could
  break parsing. Fail-soft means a break degrades to "no link", not an error; the fixture
  tests catch regressions.

---

## 8. File-change checklist
- `server_py/src/services/plive_client.py` (new)
- `server_py/src/services/plive_match.py` (new)
- `server_py/src/models.py` (+ `PliveEvent`, additive columns)
- `server_py/src/config.py` (+ `enable_westminster_video_deeplinks`, `plive_base_url`)
- Westminster `get_hansard_debate` tool (Phase W0 — attach hook)
- `server_py/src/agent/agent_shared.py` (+ Westminster source branch; `provider`/`label` on the video object)
- `server_py/src/prompts.py` (+ VIDEO TIMESTAMPS line in the Westminster worker prompt)
- `client/src/components/SourcesRail.jsx` (provider-aware Watch label) **+ `client/dist/` rebuild committed**
- `tests/` (+ fixtures + parser/matcher unit tests)
- `CLAUDE.md`, `docs/TODO.md` (docs)
- `.env` / `.env` table (new vars)

## 9. Suggested order of execution
1. **Gate on the Westminster-scope product decision (D11).** Do not start otherwise.
2. Phase 1+2 (client + lazy cache) against live endpoints, with a throwaway script first.
3. Phase 3 matcher with captured fixtures.
4. Phase 4 wire-in (depends on Phase W0's Hansard tool existing).
5. Phase 4b UI: backend `provider`/`label` on the video object → provider-aware
   `SourcesRail.jsx` Watch label + Westminster prompt line; rebuild + commit `client/dist/`.
6. Phase 5 config/tests/docs; dark-launch behind the flag; one manual browser verify.
