# Spike: Westminster (UK Parliament) video deep links — feasibility confirmation

**Type:** Read-only technical spike (HTTP probing + findings write-up). **No code, no
DB writes, no commits** beyond this doc and the findings section at the bottom.
**Estimated effort:** ~half a day.
**Scoped:** 2026-07-25. **Tracked as:** TODO.md → D11.
**Run this in a fresh session** — this doc is self-contained; you should not need prior
conversation context.

---

## 1. Why this spike exists (context for a cold start)

We built timestamped **video deep links** for the **Scottish Parliament** bot: given a
spoken contribution in the Official Report, produce a link to the exact moment in the
Scottish Parliament TV video. See the existing feature:
- Architecture: `docs/parliament/VIDEO_DEEPLINK_PLAN.md`
- Code: `server_py/src/services/sptv_client.py`, `server_py/src/services/caption_match.py`
- CLAUDE.md → "SP TV video deep links" section.

**The Scotland pipeline was hard** because SP TV exposes *no field* linking a speech to a
video time — we had to derive it from HLS WebVTT captions (segment-ordinal×6s timing,
rarest-phrase matching, DST wall-clock conversion). It only reaches ~47% coverage
because many sittings have no caption track.

**Preliminary web research (2026-07-25) suggests Westminster is fundamentally easier:**
parliamentlive.tv appears to publish a **per-speaker agenda index with precise HH:MM:SS
timecodes** natively (each entry jumps to the exact video point), backed by a structured
API at `data.parliamentlive.tv`. If true, the entire caption-derivation layer is
replaced by a lookup, and coverage is complete.

**This spike's job is to confirm that preliminary finding concretely** — turn "appears
to" into verified API shapes and URL formats — so a future build estimate is grounded.

### Important scope caveat (do NOT lose sight of this)
The parliament bot is **currently Scotland-only**. Westminster tools (`search_hansard`,
`get_hansard_debate`) were deliberately removed; `get_member_info`/`search_bills` are
Holyrood-only; `_slim_hansard_results` post-filters TWFY to `/sp/` listurls. So video
links are **not** a standalone feature — they sit on top of re-introducing Westminster
as a supported jurisdiction, which is a separate, larger product decision (see D11).
**This spike is only about the video-link feasibility layer**, so that if/when the
Westminster-scope decision is made, the video piece is already de-risked.

---

## 2. Spike goal (the three things to confirm)

Produce verified answers to exactly these, with real captured request/response samples:

- **Q1 — Per-event agenda/timecode API.** What is the machine-readable endpoint that
  returns a Westminster event's contribution list **with per-contribution timecodes**?
  Confirm the host, path, auth requirements, and JSON/XML shape. (The event page renders
  this; find the API behind it.)
- **Q2 — Hansard → video association.** Given a Hansard debate/contribution, how do we
  obtain the corresponding parliamentlive **event GUID** (and ideally the specific
  contribution's timecode)? Is the link in the Hansard API, the parliamentlive API, or
  must it be matched heuristically?
- **Q3 — Deep-link time format.** What is the exact URL format to open a parliamentlive
  video **at a given time** (and end time, if supported)? e.g. is it
  `parliamentlive.tv/Event/Index/{guid}?in=HH:MM:SS` or a query/fragment variant?

**Definition of done:** the Findings section (§6) is filled in with a concrete answer +
a captured sample for Q1, Q2, Q3, and a GO / NO-GO / CONDITIONAL recommendation with an
effort estimate for the build.

---

## 3. Known starting points (verified 2026-07-25)

- **Event page (renders the timecode index):**
  `https://www.parliamentlive.tv/Event/Index/{GUID}`
  Confirmed to show a per-speaker agenda with HH:MM:SS timecodes. Example GUID seen live:
  `23f31fe1-e45c-49d1-94b4-6af0440e7423`.
- **Event feed (Atom, lists recent events + GUIDs + watch links):**
  `http://data.parliamentlive.tv/api/event/feed` — confirmed working; Atom XML, ~30
  recent entries, each `<entry xml:base="{event URL}">` with a GUID.
- **Per-event API (NOT yet confirmed):** `http://data.parliamentlive.tv/api/event/{GUID}`
  returned **401** on first probe — wrong path or needs a header. Finding the right path
  is Q1's core task.
- **Modern Hansard JSON API:** `https://hansard-api.parliament.uk` (Open Parliament
  Licence v3.0, daily updates). Base confirmed to exist; a guessed
  `/overview/todaysdebates.json` returned 404 — find the real endpoints.
- **Members API (mature, Swagger):** `https://members-api.parliament.uk/index.html`
  (OpenAPI spec linked from that page).
- **TWFY `getHansard`:** already used in-repo (`agent/tools/parliament.py`); natively
  covers Westminster (Scotland was the bolt-on). Docs:
  `https://www.theyworkforyou.com/api/docs/getHansard`.
- **`parliament.uk` itself 403s automated fetches** — use `data.parliamentlive.tv`,
  `hansard-api.parliament.uk`, `members-api.parliament.uk` hosts, which responded.

---

## 4. Method (how to run it)

Tools: `WebFetch` (auto-markdownifies; good for HTML/JSON overview) and, where you need
raw bytes / exact JSON / custom headers, `Bash` with `curl`. **This is a dev-machine
session (has internet); the deployment target does not — reachability findings feed the
whitelist list, they are not a blocker for the spike.**

Suggested order:

1. **Resolve a concrete recent Commons event GUID** from the Atom feed
   (`data.parliamentlive.tv/api/event/feed`) so you're probing real, data-rich event.
   Prefer a Commons *Chamber* sitting (dense speaker index) over a short committee.
2. **Q1 — find the per-event API.** From the event page's rendered agenda index, work
   out the backing call. Try, with `curl -i` to see status + content-type + any auth
   hints:
   - `http://data.parliamentlive.tv/api/event/{GUID}`
   - `.../api/event/{GUID}/agenda`, `.../api/agenda/{GUID}`, `.../api/event/{GUID}/index`
   - Inspect the event page HTML source (`curl` the `/Event/Index/{GUID}` page) for the
     XHR/API URL it fetches the index from (look for `data.parliamentlive.tv` or
     `/api/` references, or a JSON blob embedded in the page).
   - If everything is 401/403, capture the exact response and note what header/cookie the
     browser sends (this determines whether it's usable server-side from the target).
3. **Q3 — deep-link time format.** On the event page, the UI has "Set Start Time / Set
   End Time" + share/link. Determine what URL that produces. Try candidates and observe
   whether the player honours them (document which you could/couldn't verify without a
   real browser): `?in=HH:MM:SS`, `?startTime=`, `#{seconds}`, `?t=`. Note: the *embed*
   iframe has been intermittently suspended by Parliament — we only need the **watch-page
   deep link**, not embed.
4. **Q2 — Hansard ↔ video mapping.** Explore `hansard-api.parliament.uk`:
   - Find the real endpoint list (try `/overview/...`, `/debates/debate/{id}.json`,
     browse from `hansard.parliament.uk` network calls). Capture a debate JSON.
   - Determine whether a debate/contribution record carries a parliamentlive event GUID,
     a "Watch" URL, or a timecode — or whether we must map by date+House+debate-title to
     the parliamentlive event, then match contribution→agenda-index entry by
     speaker+order (the fallback matching approach).
   - Sanity-check the cross-link direction from the video side too (does the
     parliamentlive per-event data reference Hansard item IDs?).
5. **Record everything in §6 as you go** — paste real (trimmed) samples, not paraphrase.

### Guardrails
- Read-only. No POSTs, no auth flows, no scraping loops — a handful of manual GETs.
- Be polite: single requests, no crawling. This is a feasibility probe, not a harvest.
- If a host needs auth we can't satisfy server-side, that's a **finding** (records a
  constraint), not a reason to work around it.

---

## 5. Decision gate (what the spike output feeds)

After §6 is filled, classify:
- **GO (cheap):** Q1+Q3 confirmed via a clean server-usable API, Q2 has a reliable
  mapping → video links are a small enrichment layer. Estimate the build (expect: an
  `plive_client.py` analogous to `sptv_client.py` but *without* the caption layer, plus
  a mapping helper and a link-attach hook in the Westminster retrieval tools).
- **CONDITIONAL:** timecodes exist but the API needs browser-only auth, or Q2 mapping is
  heuristic/unreliable → note the specific risk and what would resolve it.
- **NO-GO:** the native timecode index isn't actually machine-reachable server-side →
  Westminster would need the same caption-derivation approach as Scotland (much less
  attractive); say so plainly.

**Remember the meta-decision:** even a GO here does **not** authorise building — it
authorises *costing* the Westminster-video layer. The gating decision is still the
separate "re-introduce Westminster as a jurisdiction?" product call (D11). Feed this
spike's result into that conversation.

Update TODO.md → D11 with the outcome (GO/CONDITIONAL/NO-GO + estimate) when done.

---

## 6. Findings (spike run 2026-07-25 — read-only HTTP probing)

**Sample event used throughout:** House of Commons Chamber, 16 Jul 2026,
GUID `a44ee3be-f62c-4181-a5c4-571f91dc0b8e` (resolved from the Atom feed at
`data.parliamentlive.tv/api/event/feed`; a dense Chamber sitting — Transport orals,
UQ, statements, adjournment).

**Headline:** all three questions confirmed with clean, no-auth, server-usable
endpoints. Westminster is *fundamentally easier than Scotland* — the caption-derivation
layer (HLS/WebVTT, segment×6s timing, rarest-phrase matching) is **not needed at all**.
Both parliamentlive and Hansard expose per-agenda-item **wall-clock timecodes** on the
same timeline, and the video deep link takes a wall-clock time directly.

### Q1 — Per-event agenda/timecode API
- **Endpoint:** `GET https://www.parliamentlive.tv/Event/Logs/{GUID}` — the dedicated
  agenda/timecode index the event page loads. (Companion: `/Event/Stack/{GUID}` = same
  agenda **without** timecodes; `/Event/GetShareVideo/{GUID}?in=...` = JSON with the full
  agenda `stacks[]` + speakers + event metadata — see Q3 sample.)
  - **Dead-end (as the plan warned):** `http://data.parliamentlive.tv/api/event/{GUID}`
    → **401**; `.../agenda`, `.../index` → 404. That host only serves the Atom `feed`.
    The working route is the `www.parliamentlive.tv/Event/Logs` fragment instead — it
    supersedes the 401 API entirely, so the 401 is irrelevant.
- **Auth / headers required:** **None.** `curl` with no User-Agent, no cookie, no
  `X-Requested-With` returns `200 text/html; charset=utf-8` (272 KB fragment).
- **Server-usable from target (no browser-only cookie)?  YES.**
- **Response shape (trimmed real sample from `/Event/Logs/a44ee3be-…`):**
  ```html
  <li class="logouter">
    <div class="col-md-2 nopadding">
      <h4><span class="time-code" data-time="2026-07-16T08:33:41Z"> 09:33:41</span></h4>
    </div>
    <div class="col-md-10 nopadding"><article><header class="stack-item">
      <h4> Oral questions: Transport </h4>
    </header></article></div>
  </li>
  <li class="logouter">
    ...<span class="time-code" data-time="2026-07-16T08:35:43Z"> 09:35:43</span>...
    <h4> Simon Lightwood MP, Parliamentary Under-Secretary (Department for Transport)
         (Wakefield and Rothwell, Labour (Co-op)) </h4>
  </li>
  ```
- **Per-contribution timecode present? field:** **YES** — `data-time` on
  `<span class="time-code">` = **UTC** ISO (`…08:33:41Z`); the visible text is the
  **BST local** render (`09:33:41`). Each `<li class="logouter">` pairs a timecode with
  the agenda item / speaker (name + role + constituency + party). Granularity is
  agenda-item / new-speaker (not literally every sentence) — comparable to SP's index.
  It's an HTML fragment, not JSON, but fully structured and trivially parseable.

### Q2 — Hansard → parliamentlive mapping
- **Hansard API endpoint(s) used** (`https://hansard-api.parliament.uk`, OPL v3.0, no
  auth; endpoint list from `/swagger/docs/v1`):
  - `GET /overview/sectiontrees.json?house=Commons&date=2026-07-16&section=Debate&groupByOwner=true`
    — day's debate tree; each node has `ExternalId` + a `Timecode` field.
  - `GET /debates/debate/{debateSectionExtId}.json` — full debate with contributions
    (`AttributedTo`, `MemberId`, `Value`, `OrderInSection`, `Timecode`).
  - `GET /search/debates.json?queryParameters.searchTerm=…&…startDate=…&…house=Commons`
    — term → `DebateSectionExtId` (verified: `e-bikes` → `42B6F270-…`).
- **Direct association field (GUID / watch URL / timecode)?  PARTIAL.**
  - Hansard carries a **`Timecode`** on debate sections — **wall-clock, same timeline as
    parliamentlive** (real sample: `"Timecode":"2026-07-16T09:45:39"`, i.e. local BST, no
    `Z`; parliamentlive's `data-time` for the same instant is `08:45:39Z`). So Hansard's
    own timecode *is* the video `?in=` value directly.
  - **BUT** Hansard does **not** carry a parliamentlive **event GUID** or watch URL (no
    video/watch/player field anywhere in the debate JSON). And `Timecode` is populated at
    **section / agenda-item level**, not on every individual `Contribution` (in the
    sample: 66 populated vs 200 null — nulls are the fine-grained per-speech items).
- **If no direct link — matching strategy (confirmed working):**
  1. **date + House → event GUID:** `GET https://www.parliamentlive.tv/Search?House=Commons&Start=16%2F07%2F2026&End=16%2F07%2F2026`
     returns a 50 KB results page listing that day's events as `Event/Index/{GUID}` links.
     Verified: it returned exactly the day's Commons events incl. the Chamber
     `a44ee3be-…`, Westminster Hall `9eb642a7-…`, PAC, two Health Bill committees. Pick
     the event by business/title (one **Chamber** event per House per day ⇒ unambiguous
     for chamber debates; committees disambiguate by committee name).
  2. **contribution → time:** use Hansard's section `Timecode` directly, **or** for finer
     granularity match Hansard `AttributedTo`/`OrderInSection` against the
     `/Event/Logs/{GUID}` index by speaker + order (both share wall-clock, so a coarse
     time bound makes the match robust).
- **Reliability assessment:** **High for chamber debates.** The two sources share an
  identical wall-clock timeline and the date+House→GUID lookup is deterministic for
  chamber sittings. The only fuzziness is *sub-item* precision (Hansard timecodes are
  per-section, not per-sentence) — acceptable, and improvable via the Logs index. Main
  residual risk is committee disambiguation (several committees per day → match on
  committee name/time), same class of problem already solved for SP committees.

### Q3 — Deep-link time format
- **Working URL format:** `https://parliamentlive.tv/event/index/{GUID}?in=HH:MM:SS`
  (local wall-clock time). This is the **canonical share URL the site itself generates**.
- **Start + end time supported?  YES:** `?in=HH:MM:SS&out=HH:MM:SS`.
- **Verified how:** via the site's own share-link generator
  `GET /Event/GetShareVideo/{GUID}?in={ISO}&out={ISO}`, which returns the authoritative
  `pageUrl`. Real sample (start+end):
  ```json
  {
    "pageUrl": "https://parliamentlive.tv/event/index/a44ee3be-f62c-4181-a5c4-571f91dc0b8e?in=09:35:43&out=09:36:45",
    "requestedInPoint": "2026-07-16T08:35:43Z",
    "requestedOutPoint": "2026-07-16T08:36:45Z",
    "embedCode": "<iframe src=\"https://videoplayback.parliamentlive.tv/Player/Index/{GUID}?in=2026-07-16T09%3A35%3A43%2B01%3A00&audioOnly=False&autoStart=False&script=False\" ...>",
    "stacks": [ {"description":"Oral questions: Transport","iasDisplayAs":"","sortOrder":1},
                {"description":"Q1. …e-bikes… (901043)","iasDisplayAs":"Ms Julie Minns MP (Carlisle, Labour)","sortOrder":2}, … ],
    "event": {"house":"Commons","business":"Chamber","room":"Commons Chamber",
              "actualStartTime":"2026-07-16T08:00:00Z", "states":{"playerState":"ARCHIVE"} }
  }
  ```
  Note the two encodings: the **watch page** takes a bare local `?in=HH:MM:SS`; the
  **embed iframe** (on `videoplayback.parliamentlive.tv`, sometimes suspended) takes a
  full ISO `?in=2026-07-16T09:35:43+01:00`. We only need the watch-page deep link.
  We produce it directly from a Hansard/Logs timecode — no call to `GetShareVideo`
  needed at query time (that endpoint is just how the site's "Share" panel builds it).

### Reachability / whitelist implications (for the internet-restricted target)
Hosts that must be whitelisted:
- **`www.parliamentlive.tv`** — required. Serves `/Event/Logs/{GUID}` (timecodes),
  `/Event/Stack`, `/Event/GetShareVideo`, and `/Search` (date+House→GUID).
- **`hansard-api.parliament.uk`** — required. Debate JSON + search (the Westminster
  Hansard retrieval layer this sits on would need it regardless).
- **`data.parliamentlive.tv`** — optional (only the Atom `feed`; not needed if using
  `/Search` for GUID lookup).
- **`parliamentlive.tv`** (bare host) — the deep-link URL we *emit to users*; users'
  browsers hit it, the server does not, so not a server-whitelist item.
- **`videoplayback.parliamentlive.tv`** — only for embed iframes (not needed for
  watch-page deep links).
- `parliament.uk` itself still 403s automated fetches — not used by this pipeline.

### Recommendation
- **GO (cheap).** Q1 + Q3 confirmed via clean, no-auth, server-usable endpoints; Q2 has
  a deterministic mapping for chamber debates. The whole SP TV caption-derivation layer
  is **eliminated** — no HLS, no WebVTT, no segment×6s, no rarest-phrase matching, no
  ~47% caption-coverage ceiling. Coverage is effectively complete for archived events.
- **Build effort estimate (video layer only): ~2–3 days.**
  - `plive_client.py` (analogous to `sptv_client.py` but *no* caption layer): resolve
    date+House → event GUID via `/Event/Search`-style GET; fetch + parse `/Event/Logs`
    into `[(utc_time, local_time, agenda/speaker)]`. (~1 day)
  - Mapping helper: Hansard debate/contribution → `?in=HH:MM:SS` deep link, using the
    section `Timecode` directly, with optional speaker+order match against the Logs index
    for finer placement; DST-correct local render (reuse the `zoneinfo` logic pattern from
    Scotland). (~0.5 day)
  - Link-attach hook in the (to-be-reintroduced) Westminster retrieval tools + fail-soft
    behaviour + a small cache table analogous to `sp_video_captions` keyed by event GUID.
    (~0.5–1 day)
  - Tests against 1–2 captured fixtures (a Logs fragment + a debate JSON). (~0.5 day)
- **Key risks / unknowns remaining:**
  - **Not browser-verified playback.** `?in=`/`&out=` confirmed via the site's *own*
    share-URL generator (authoritative), but I could not drive a real player to watch it
    seek. Low risk — it's the site's canonical share link.
  - **Sub-item precision.** Hansard `Timecode` is per-section, not per-sentence; exact
    speech-level placement needs the Logs-index speaker match. Acceptable for an MVP.
  - **Committee disambiguation** (several committees/day) — solvable by committee-name
    match, same pattern as SP committees.
  - **Historical GUID coverage** — verified for a recent sitting; older events should
    resolve via `/Search` date range, but the depth of the archive wasn't probed.
  - **⚠️ This GO authorises *costing only*, not building.** The gating decision is the
    separate product call: **re-introduce Westminster as a supported jurisdiction?**
    (Hansard tools, crawl/search layer, filter/session plumbing, prompt scope were all
    deliberately removed — that ~Scotland-sized scope is the real cost, and the reason
    for the original removal must be understood first.) The video layer is the last ~10%
    on top, and this spike de-risks it.
