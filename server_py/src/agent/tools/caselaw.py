"""National Archives case law: Atom feed and LegalDocML (AKN) judgment parsing."""

import re
import xml.etree.ElementTree as ET
from typing import Optional

import httpx


_ATOM_NS = "http://www.w3.org/2005/Atom"
# The Atom feed's TNA extension elements (<tna:identifier>, etc.) live on the bare
# host namespace. (Earlier code read <uk:ncn>/<uk:court> from a /terms/v1 URI that the
# feed never uses, so ncn/court came back empty on every live result.)
_TNA_NS = "https://caselaw.nationalarchives.gov.uk"
# The judgment data.xml carries the neutral citation in <uk:cite> on the AKN namespace.
_TNA_AKN_NS = "https://caselaw.nationalarchives.gov.uk/akn"


# Court-level ranks for appeal detection. Higher rank = higher (appellate) court.
# Keyed on the court code that appears in a neutral citation (NCN) or the <uk:court>
# field, e.g. "[2025] EWCA Civ 1671" -> EWCA -> rank 3. Only what we need to tell a
# first-instance judgment apart from its appeal; unlisted courts rank 0 (ignored).
_COURT_RANK = {
    "UKSC": 4, "UKPC": 4,        # Supreme Court / Privy Council
    "EWCA": 3, "CSIH": 3, "NICA": 3,  # Court of Appeal / Inner House / NI Court of Appeal
    "EWHC": 2, "CSOH": 2, "UKUT": 2,  # High Court / Outer House / Upper Tribunal
}

# Generic legal/institutional words that are not distinctive party identifiers.
# A shared surname like "coulthard" links a case to its appeal; shared boilerplate
# like "secretary" or "home department" must not — two unrelated judicial reviews
# against the same government department should not read as one litigation. The
# distinctive signal is a private party name, which also survives party-order flips
# on appeal (claimant may become appellant), so matching stays on both sides.
_PARTY_STOPWORDS = {
    # court/procedural boilerplate
    "application", "another", "others", "regina", "rex", "appellant",
    "respondent", "appellants", "respondents", "claimant", "defendant",
    # office-holders and institutions
    "secretary", "state", "department", "departments", "minister", "ministers",
    "attorney", "general", "government", "council", "commissioners",
    "commissioner", "authority", "board", "trust", "trusts", "service",
    "services", "national", "united", "kingdom", "limited", "company",
    "companies", "majesty", "majestys", "revenue", "customs", "office",
    "advocate", "chancellor", "director", "prosecutions", "chief", "constable",
    "prime", "governor", "prison", "prisons", "police", "executive", "agency",
    # common UK government department / policy-area words
    "home", "environment", "food", "rural", "affairs", "work", "pensions",
    "health", "care", "justice", "defence", "transport", "education",
    "treasury", "housing", "communities", "levelling", "culture", "media",
    "sport", "business", "trade", "digital", "foreign", "commonwealth",
    "development", "revenue",
}


def _court_rank(ncn: str, court: str, url: str = "") -> int:
    """Return the court-hierarchy rank for a result (0 = unknown).

    Derives the court code from the NCN/court fields *and* the judgment URL. Live
    National Archives Atom feeds do not populate <uk:ncn>/<uk:court>, but the court
    is always in the URL path (e.g. .../ewca/civ/2025/1671 -> EWCA), so scanning the
    URL is what makes appeal detection work on real search results, not just on
    hand-built test dicts.
    """
    text = f"{ncn} {court} {url}".upper()
    for code, rank in _COURT_RANK.items():
        if code in text:
            return rank
    return 0


def _party_tokens(title: str) -> set[str]:
    """Distinctive party-name tokens from a case title (surnames etc.), lower-cased.

    Alphabetic tokens of length >=4 minus generic legal/institutional stopwords, so
    two records of the same litigation share their distinctive party surname(s).
    """
    toks = re.findall(r"[a-z]{4,}", title.lower())
    return {t for t in toks if t not in _PARTY_STOPWORDS}


def detect_appellate_decisions(results: list[dict]) -> list[dict]:
    """Find search results that are the appellate decision of another result in the set.

    Retrieving a case's appeal is otherwise search luck: when both the first-instance
    judgment and its appeal appear in the same result set, the model may cite only the
    lower court. This flags each higher-court result (EWCA/UKSC etc.) that shares a
    distinctive party name with a lower-court result, so the caller can nudge the model
    to retrieve the appellate decision. Returns the appellate results in input order.
    """
    enriched = []
    for r in results:
        if not r.get("url"):
            continue
        enriched.append({
            "r": r,
            "rank": _court_rank(r.get("ncn", ""), r.get("court", ""), r.get("url", "")),
            "tokens": _party_tokens(r.get("title", "")),
        })

    # How many results each token appears in — a party surname is rare (the case and
    # its appeal); common words that slip through the stopword list are not distinctive.
    freq: dict[str, int] = {}
    for e in enriched:
        for t in e["tokens"]:
            freq[t] = freq.get(t, 0) + 1

    appellate: list[dict] = []
    seen_urls: set[str] = set()
    for hi in enriched:
        if hi["rank"] < 3:  # only nudge toward genuinely appellate courts
            continue
        url = hi["r"]["url"]
        if url in seen_urls:
            continue
        for lo in enriched:
            if lo is hi or lo["rank"] == 0 or lo["rank"] >= hi["rank"]:
                continue
            shared = {t for t in (hi["tokens"] & lo["tokens"]) if freq[t] <= 3}
            if shared:
                appellate.append(hi["r"])
                seen_urls.add(url)
                break
    return appellate


def _parse_case_law_atom(xml_text: str) -> list[dict]:
    """Parse a National Archives case law Atom feed into a list of slim judgment dicts."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    entries = []
    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        title = entry.findtext(f"{{{_ATOM_NS}}}title", "")
        url_el = entry.find(f"{{{_ATOM_NS}}}link[@rel='alternate']")
        if url_el is None:
            url_el = entry.find(f"{{{_ATOM_NS}}}link")
        url = (
            url_el.get("href", "")
            if url_el is not None
            else entry.findtext(f"{{{_ATOM_NS}}}id", "")
        )
        published = entry.findtext(f"{{{_ATOM_NS}}}published", "")
        # The neutral citation is the text of <tna:identifier type="ukncn"> and its
        # court path is that element's slug attribute, e.g.
        #   <tna:identifier slug="ewca/civ/2025/1671" type="ukncn">[2025] EWCA Civ 1671</...>
        # (namespace https://caselaw.nationalarchives.gov.uk — NOT the /terms/v1 URI, and
        # there is no <court> element at all: earlier code read both from the wrong
        # namespace and got empty strings, so ncn/court were blank on every live result).
        ncn = ""
        court = ""
        for ident in entry.findall(f"{{{_TNA_NS}}}identifier"):
            if ident.get("type") == "ukncn":
                ncn = (ident.text or "").strip()
                slug = ident.get("slug", "")
                court = slug.rsplit("/", 2)[0] if slug else ""  # "ewca/civ/2025/1671" -> "ewca/civ"
                break
        entries.append({
            "title": title,
            "ncn": ncn,
            "court": court,
            "date": published[:10] if published else "",
            "url": url,
        })
    return entries


# ---------------------------------------------------------------------------
# P3.23: how many judgments matched, not how many were shown
# ---------------------------------------------------------------------------
#
# `search_case_law` used to return `"total": len(entries)`, never more than the
# 50-row page, so a model reading `total: 50` believed it had seen every match
# when the feed may hold thousands. The real figure is in the feed's `last`
# link, and **it is computed at ten judgments a page, whatever page size was
# asked for** (measured live 2026-10-05, batch 7 D): a one-word surname query
# returns 50 rows a page and `last` page 520, with or without `per_page=50`; the true count,
# found by paging, is 5,193, and page 520 at `per_page=10` holds exactly 3.
# Read at the page size requested, the same link said "up to 26,000" and the
# last pages came back empty, which is the "the last page can be empty" that
# P3.23's row recorded. At ten a page the total is known to within ten.
#
# A page holding fewer rows than the page size is the whole matching set,
# whatever the link says (a dated query showed 19 rows with `last` page 2).
CASE_LAW_PAGE_SIZE = 50          # the page size we ask for (P3.22 sends `per_page`)
_LAST_LINK_PAGE_SIZE = 10        # the page size the `last` link counts in


def _parse_case_law_last_page(xml_text: str) -> Optional[int]:
    """The page number in the feed's `<link rel="last">`, or None."""
    from urllib.parse import parse_qs, urlparse

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    for link in root.findall(f"{{{_ATOM_NS}}}link"):
        if link.get("rel") != "last":
            continue
        try:
            page = parse_qs(urlparse(link.get("href", "")).query).get("page")
            return int(page[0]) if page else None
        except (ValueError, TypeError):
            return None
    return None


def case_law_count(xml_text: str, shown: int, page_size: int = CASE_LAW_PAGE_SIZE) -> dict:
    """The shown count and the matching total, kept apart (P1.3's split).

    `total` is the best figure for how many judgments match: exact where it is
    known (a page that is not full holds the whole set), otherwise the upper
    end of the range the `last` link gives (`total_min` to `total_max`). With
    no usable `last` link on a full page, `total` stays the shown count and
    `total_exact` is False, so a consumer reading `total` as an int still gets
    one. Callers deciding whether anything was returned key on `shown`, never on
    `total` (P3.23's constraint).
    """
    if shown < page_size:
        return {"shown": shown, "total": shown, "total_exact": True,
                "total_min": shown, "total_max": shown}
    last = _parse_case_law_last_page(xml_text)
    if not last or last < 1:
        return {"shown": shown, "total": shown, "total_exact": False,
                "total_min": shown, "total_max": None}
    lo = max(shown, (last - 1) * _LAST_LINK_PAGE_SIZE + 1)
    hi = max(shown, last * _LAST_LINK_PAGE_SIZE)
    return {"shown": shown, "total": hi, "total_exact": lo == hi,
            "total_min": lo, "total_max": hi}


# ---------------------------------------------------------------------------
# P3.22: the order the feed lists results in
# ---------------------------------------------------------------------------
#
# With no `order`, the feed lists newest first (`-date`), so every case-law
# search until P3.22 handed the model the 50 most recent matches rather than
# the 50 most relevant, and the Phase-2 nudge's "most relevant" first three
# were the three newest. Measured live over every stored query (batch 8 C,
# 2026-10-06): relevance keeps the matching set (304 of 304 short pages the
# same rows, 52 of 52 full pages the same `last` link) and changes the first
# three about seven times in ten.
#
# **`order=relevance` is the advanced search's own sort and is NOT in the
# published API spec**: `public_api.yml` v0.6.0 (re-read 2026-10-06) lists
# `order` as `date`, `updated` or `transformation` (with `-` forms; default
# `-date`). It is what the feed does, and `tools/caselaw_probe.check_order`
# re-checks it live, so a withdrawal (the list coming back newest first) is
# seen rather than silently returning the old order.
#
# **The two params travel together.** ANY explicit `order` resets the page
# size to 10 unless `per_page` is sent with it (that is why relevance once
# looked like it cut 50 results to 10), and `last` still counts at ten a page
# under either order, so `case_law_count` is unchanged. A test pins both.
CASE_LAW_ORDER_PARAMS = {"order": "relevance", "per_page": str(CASE_LAW_PAGE_SIZE)}


# ---------------------------------------------------------------------------
# P3.9: the date filter the feed honours
# ---------------------------------------------------------------------------
#
# `search_case_law` sent `date_from`/`date_to`, and the feed ignores both (as it
# ignores `from_date`/`to_date`): a 2025-only window returned the same 50
# results as no window at all, so the model's per-query dates and the lawyer's
# date range, intersected into the same params, silently did nothing. **The
# form that works is the advanced search's day/month/year triple,
# `from_date_0/1/2` and `to_date_0/1/2`, and it is NOT in the published API
# spec** (`public_api.yml` documents no date parameter at all; batch 5 C,
# `docs/LEGAL_DATA_SOURCES.md` section 4). It is what the feed does, verified
# live 2026-09-18 and 2026-10-05, and `tools/caselaw_probe.py` re-checks it, so
# a withdrawal is seen rather than silently turning the filter off again.

def _parse_case_law_date(value, end: bool):
    """`YYYY-MM-DD`, or `YYYY-MM` / `YYYY` widened to the month or year (its
    first day for a start, its last for an end). Raises ValueError otherwise."""
    import calendar
    import re as _re
    from datetime import date

    s = str(value).strip()
    m = _re.fullmatch(r"(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?", s)
    if not m:
        raise ValueError(s)
    y = int(m.group(1))
    if m.group(3):
        return date(y, int(m.group(2)), int(m.group(3)))
    if m.group(2):
        mo = int(m.group(2))
        return date(y, mo, calendar.monthrange(y, mo)[1] if end else 1)
    return date(y, 12, 31) if end else date(y, 1, 1)


def case_law_date_window(args: dict, cfg: dict) -> dict:
    """The date window a case-law search runs under, and the params that apply it.

    The model's `date_from`/`date_to` are INTERSECTED with the lawyer's date
    range (`_date_from`/`_date_to`): the later start and the earlier end win,
    as before P3.9. Returns `{"params", "dates", "error"}`: `params` are the
    feed's `from_date_0/1/2` / `to_date_0/1/2` (day, month, year); `dates` is
    the applied window as ISO strings (None for an open end), for the result
    and the window note; `error` is set, and nothing is to be sent, when a date
    is not a date or the window is empty (a start after its end; the case-law
    twin of `docs/TODO.md` D16 defect 1, which stays parked for legislation).
    """
    args, cfg = args or {}, cfg or {}
    bounds = {}
    for key, user_key, end in (("date_from", "_date_from", False),
                               ("date_to", "_date_to", True)):
        got = []
        for who, raw in (("the dates asked for", args.get(key)),
                         ("the lawyer's dates", cfg.get(user_key))):
            if raw in (None, ""):
                continue
            try:
                got.append(_parse_case_law_date(raw, end))
            except ValueError:
                return {"params": {}, "dates": None, "error": (
                    f"{key} '{raw}' ({who}) is not a date in YYYY-MM-DD form, so "
                    "no search was run. Search again with dates in that form.")}
        bounds[key] = (min(got) if end else max(got)) if got else None
    lo, hi = bounds["date_from"], bounds["date_to"]
    if lo and hi and lo > hi:
        both = bool(cfg.get("_date_from") or cfg.get("_date_to"))
        return {"params": {}, "dates": None, "error": (
            f"The date window is empty: it would run from {lo.isoformat()} to "
            f"{hi.isoformat()}"
            + (" once the dates asked for are combined with the dates the lawyer "
               "set for this research" if both else "")
            + ", so no search was run. Search again with a start date on or "
              "before the end date.")}
    params = {}
    for prefix, d in (("from_date", lo), ("to_date", hi)):
        if d:
            params.update({f"{prefix}_0": str(d.day), f"{prefix}_1": str(d.month),
                           f"{prefix}_2": str(d.year)})
    dates = ({"from": lo.isoformat() if lo else None, "to": hi.isoformat() if hi else None}
             if (lo or hi) else None)
    return {"params": params, "dates": dates, "error": None}


def _extract_judgment_text(xml_text: str) -> str:
    """Extract plain text from a LegalDocML (AKOMA NTOSO) XML judgment."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ""
    parts = []
    for el in root.iter():
        if el.text and el.text.strip():
            parts.append(el.text.strip())
        if el.tail and el.tail.strip():
            parts.append(el.tail.strip())
    return "\n".join(parts)


async def _fetch_judgment_text(url: str, client: Optional[httpx.AsyncClient] = None) -> dict:
    """Fetch and return the full text of a National Archives judgment via its data.xml URL.

    P4.19: the GET goes through `_request_with_retry` (A5a), so a 429 under
    the National Archives' per-IP limit (1,000 requests per rolling five
    minutes) is retried with backoff, honouring `Retry-After`, instead of
    reaching `raise_for_status()` as a dropped retrieval. `client` is the
    executor's; without one, a client is opened here as before. The 15 s
    timeout is kept per request, whichever client carries it.
    """
    # Imported here, not at the top: `executor` imports this module.
    from .executor import _request_with_retry

    data_url = url.rstrip("/") + "/data.xml"
    if client is None:
        async with httpx.AsyncClient(timeout=15.0, verify=False) as own:
            resp = await _request_with_retry(
                own, "GET", data_url, name="get_case_law_text", timeout=15.0
            )
    else:
        resp = await _request_with_retry(
            client, "GET", data_url, name="get_case_law_text", timeout=15.0
        )
    resp.raise_for_status()
    text = _extract_judgment_text(resp.text)
    # Extract title (FRBRname/@value) and neutral citation (<uk:cite> text) from the
    # AKN judgment XML. Earlier code read the NCN from a non-existent /terms/v1 element,
    # so it always returned "".
    try:
        root = ET.fromstring(resp.text)
        ncn = (root.findtext(f".//{{{_TNA_AKN_NS}}}cite") or "").strip()
        title_el = root.find(".//{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}FRBRname")
        title = title_el.get("value", "") if title_el is not None else ""
    except Exception:
        ncn = ""
        title = ""
    return {"url": url, "title": title, "ncn": ncn, "text": text}

