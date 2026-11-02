"""National Archives case law: Atom feed and LegalDocML (AKN) judgment parsing."""

import re
import xml.etree.ElementTree as ET
from functools import lru_cache
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


# P3.29: the detector linked a case and its "appeal" on ANY one shared party word
# outside the stopword list, so a place, "county", "holdings" or a first name
# linked unrelated cases: over every stored result set and batch 8 C's re-run
# (748 distinct sets), 106 of the 317 distinct appeals it flagged were the same
# litigation at two levels, read by hand (evidence/seam/s52/p329). Three checks
# now stand between a shared word and a link (after: 105 of 107):
#
# 1. The words. `_APPEAL_NAME_NOISE` is the generic vocabulary of party names in
#    the corpus: places and local-government words, corporate forms, and the
#    procedural and institutional words, read off the most frequent title words of
#    every stored result. It is the appeal detector's own list:
#    `_PARTY_STOPWORDS` also feeds P3.46's named-case note, which is unchanged.
# 2. The parties. One shared name word is enough only where the OTHER party
#    agrees too ("Payne v SSWP" and "SSWP v Payne"; "Smith v RBS" and "Karen
#    Smith v The RBS"), so "Berezovsky v Hine" is not the appeal of "Berezovsky v
#    Abramovich" and "R (Best) v SSJ" not that of "Best v Chief Land Registrar".
#    Two shared name words are enough unless the other parties are named
#    differently ("Tesco v USDAW" and "Nistor v USDAW"; "Dawn Bunyan (Valuation
#    Officer) v Fridays" and "Stanuszek v Dawn Bunyan (Listing Officer)"). A title whose every name
#    word is generic ("British Telecommunications plc v HM Treasury") links on
#    the same two parties, never on two-letter initials alone ("AM v SSHD").
#    Lost by this, read: an appeal whose respondent was a co-defendant below
#    ("Woodland v Essex CC" from "Woodland v Swimming Teachers' Association & Ors").
# 3. The dates and the court. An appeal is decided after the judgment under
#    appeal and within `_APPEAL_MAX_GAP_DAYS` of it; a result whose date is missing
#    is not refused on the date. The Court of Appeal (Criminal Division) and the
#    Privy Council hear no appeal from a court the feed lists, so neither is
#    flagged.
#
# The set-frequency filter (a word in more than three results was dropped) is
# gone: it removed the surname of a litigant with several judgments in one set
# ("Evans v First Secretary of State") while keeping "county".
_APPEAL_NAME_NOISE = frozenset({
    # places and local government
    "london", "borough", "boroughs", "city", "county", "district", "metropolitan",
    "north", "south", "east", "west", "northern", "southern", "eastern", "western",
    "royal", "parish", "mayor", "burgesses", "commonalty", "commonality", "citizens",
    "scotland", "scottish", "england", "english", "wales", "welsh", "ireland",
    "irish", "britain", "british", "great", "greater", "europe", "european",
    "international", "global", "central", "upon", "local", "community",
    # corporate forms and common business words
    "group", "holdings", "holding", "bank", "banking", "finance", "financial",
    "capital", "investments", "investment", "properties", "property", "estates",
    "estate", "homes", "partners", "partnership", "management", "corporation",
    "corporate", "insurance", "assurance", "trading", "commercial", "developments",
    "construction", "solutions", "enterprises", "ventures", "industries",
    "industrial", "energy", "water", "utilities", "infrastructure",
    "telecommunications", "networks", "network", "markets", "centre", "center",
    "house", "land", "park", "parks", "street", "road", "square", "gardens",
    "foundation", "association", "society", "institute", "university", "college",
    "school", "club", "union", "alliance", "fund", "scheme", "pension", "firm",
    "stores", "shop", "retail", "hotels", "logistics", "technology", "resources",
    "engineering", "airways", "maritime", "rail", "mutual", "opportunities",
    # procedural and institutional words
    "anor", "matter", "information", "court", "courts", "crown", "magistrates",
    "sitting", "tribunal", "chamber", "first", "tier", "entitlement", "social",
    "officer", "officers", "valuation", "listing", "registrar", "solicitors",
    "regulation", "regulatory", "commission", "ministry", "cabinet", "exchequer",
    "lord", "lords", "queen", "king", "public", "criminal", "civil", "legal",
    "judicial", "review", "rights", "child", "children", "mother", "father",
    "persons", "unknown", "claimants", "deceased", "liquidation", "administration",
    "insolvency", "joint", "liquidators", "administrators", "receiver", "official",
    "trustees", "trustee", "formerly", "known", "behalf", "representative", "hmrc",
    "inland", "excise", "conduct", "security", "protection", "independent",
    "natural", "hospital", "hospitals", "healthcare", "constabulary", "workers",
    "action", "litigation", "strategy", "consulting", "generation", "contract",
    "contracts", "climate", "change",
})

# Six years: the longest gap between a judgment and its appeal among the
# genuine pairs read was 3.3 years (EWHC to UKSC); a chain through the Court of
# Appeal can take longer.
_APPEAL_MAX_GAP_DAYS = 6 * 365 + 2

# Words of an opposing party that do not identify it.
_SIDE_JOINERS = frozenset({
    "the", "of", "for", "and", "on", "in", "at", "to", "by", "as", "an", "re", "ex",
    "parte", "application", "anor", "ors", "others", "another", "ltd", "limited",
    "plc", "llp", "inc", "rev", "trading",
})


@lru_cache(maxsize=4096)
def _title_parts(title: str) -> tuple[str, ...]:
    """Each party of a title, lower-cased ("X v Y" gives two; a title with no
    "v", such as "Re X", gives one)."""
    return tuple(re.split(r"\s+v\.?\s+", (title or "").lower())[:2])


@lru_cache(maxsize=4096)
def _appeal_name_tokens(title: str) -> frozenset[str]:
    """Party-name words that can identify a litigant: `_party_tokens` less the
    corpus's generic party-name vocabulary."""
    return frozenset(_party_tokens(title) - _APPEAL_NAME_NOISE)


@lru_cache(maxsize=4096)
def _title_sides(title: str) -> tuple[frozenset[str], ...]:
    """The words of each party in a title, less joiners and corporate suffixes."""
    return tuple(frozenset(w for w in re.findall(r"[a-z]{2,}", p) if w not in _SIDE_JOINERS)
                 for p in _title_parts(title))


def _word_hit(w: str, other: set[str]) -> bool:
    """A word is on the other side when it is there, or matches a word it begins
    or that begins it (four letters or more: "work"/"works", "syke"/"sykes")."""
    return any(w == o or (min(len(w), len(o)) >= 4 and (w.startswith(o) or o.startswith(w)))
               for o in other)


def _words_agree(a: set[str], b: set[str]) -> bool:
    """Two parties' words agree when more than half the shorter side's words are
    on the other side."""
    if not a or not b:
        return False
    small, big = (a, b) if len(a) <= len(b) else (b, a)
    return sum(1 for w in small if _word_hit(w, big)) * 2 > len(small)


def _other_parties_agree(hi_title: str, lo_title: str, token: str) -> bool:
    """For one shared name word: the party it names in each title, and the
    OTHER party in each title agrees. A title with one party only cannot be
    checked and does not agree."""
    hs, ls = _title_sides(hi_title), _title_sides(lo_title)
    if len(hs) < 2 or len(ls) < 2:
        return False
    hi_idx = [i for i, s in enumerate(hs) if token in s]
    lo_idx = [i for i, s in enumerate(ls) if token in s]
    return any(_words_agree(hs[1 - i], ls[1 - j]) for i in hi_idx for j in lo_idx)


def _identifies(a: set[str], b: set[str]) -> bool:
    """The words two agreeing parties share name somebody: a word of three
    letters or more that is not a government office or court word. Two-letter
    initials ("AM v SSHD", "MM v SSHD") are shared by unrelated anonymised
    claimants against the same department."""
    return any(len(w) >= 3 and w not in _PARTY_STOPWORDS and _word_hit(w, b) for w in a)


def _same_parties(hi_title: str, lo_title: str) -> bool:
    """Both parties of two-party titles agree, in either order (the claimant may
    be the respondent on appeal), and their shared words name somebody: the
    route for a title whose every name word is generic ("British
    Telecommunications plc v HM Treasury")."""
    hs, ls = _title_sides(hi_title), _title_sides(lo_title)
    if len(hs) < 2 or len(ls) < 2:
        return False
    for a0, a1, b0, b1 in ((hs[0], hs[1], ls[0], ls[1]), (hs[0], hs[1], ls[1], ls[0])):
        if (_words_agree(a0, b0) and _words_agree(a1, b1)
                and (_identifies(a0, b0) or _identifies(a1, b1))):
            return True
    return False


def _other_parties_differ(hi_title: str, lo_title: str, shared: set[str]) -> bool:
    """The shared words name one party in each title, and the OTHER parties are
    named differently: each has a name word, they share none and their words do
    not agree ("Tesco v USDAW" and "Nistor v USDAW"). A generic other party
    ("Secretary of State ... & Ors") never differs."""
    hp, lp = _title_parts(hi_title), _title_parts(lo_title)
    if len(hp) < 2 or len(lp) < 2:
        return False
    hs, ls = _title_sides(hi_title), _title_sides(lo_title)
    hi_idx = [i for i, s in enumerate(hs) if s & shared]
    lo_idx = [i for i, s in enumerate(ls) if s & shared]
    if not hi_idx or not lo_idx:
        return False
    for i in hi_idx:
        for j in lo_idx:
            a = _appeal_name_tokens(hp[1 - i])
            b = _appeal_name_tokens(lp[1 - j])
            if not a or not b or a & b or _words_agree(hs[1 - i], ls[1 - j]):
                return False
    return True


def _names_match(hi_title: str, lo_title: str) -> bool:
    """The same litigation by its names: two shared name words, the other
    parties not named differently; one, with the other party agreeing; or the
    same two parties."""
    shared = _appeal_name_tokens(hi_title) & _appeal_name_tokens(lo_title)
    if len(shared) >= 2 and not _other_parties_differ(hi_title, lo_title, shared):
        return True
    if any(_other_parties_agree(hi_title, lo_title, t) for t in shared):
        return True
    return _same_parties(hi_title, lo_title)


def _decision_date(r: dict):
    from datetime import date
    try:
        return date.fromisoformat(str(r.get("date") or "")[:10])
    except ValueError:
        return None


def _hears_no_listed_appeal(r: dict) -> bool:
    """The Court of Appeal (Criminal Division) hears appeals from the Crown Court
    and the Privy Council from overseas courts: neither is the appeal of a
    judgment the feed lists."""
    text = f"{r.get('ncn', '')} {r.get('court', '')} {r.get('url', '')}".upper()
    return "EWCA CRIM" in text or "EWCA/CRIM" in text or "UKPC" in text


def _dates_allow_appeal(hi: dict, lo: dict) -> bool:
    hd, ld = _decision_date(hi), _decision_date(lo)
    if hd is None or ld is None:
        return True
    return 0 <= (hd - ld).days <= _APPEAL_MAX_GAP_DAYS


def _appeal_pairs(results: list[dict]) -> list[tuple[dict, dict]]:
    """Every (appeal, judgment under appeal) pair in a result set, appeals in
    input order: a higher-court result (Court of Appeal, Inner House, Supreme
    Court) and a lower-court result naming the same litigant, decided in an
    order and within a time an appeal allows (P3.29, above)."""
    enriched = []
    for r in results:
        if not isinstance(r, dict) or not r.get("url"):
            continue
        enriched.append({
            "r": r,
            "rank": _court_rank(r.get("ncn", ""), r.get("court", ""), r.get("url", "")),
            "title": r.get("title", "") or "",
        })
    out: list[tuple[dict, dict]] = []
    for hi in enriched:
        if hi["rank"] < 3 or _hears_no_listed_appeal(hi["r"]):
            continue
        for lo in enriched:
            if lo is hi or lo["rank"] == 0 or lo["rank"] >= hi["rank"]:
                continue
            if not _dates_allow_appeal(hi["r"], lo["r"]):
                continue
            if _names_match(hi["title"], lo["title"]):
                out.append((hi["r"], lo["r"]))
    return out


def detect_appellate_decisions(results: list[dict]) -> list[dict]:
    """Find search results that are the appellate decision of another result in the set.

    Retrieving a case's appeal is otherwise search luck: when both the first-instance
    judgment and its appeal appear in the same result set, the model may cite only the
    lower court. This flags each higher-court result (EWCA/UKSC etc.) that is the
    appeal of a lower-court result in the set (`_appeal_pairs`: the same litigant,
    the dates in an appeal's order, a court that hears such an appeal), so the
    caller can nudge the model to retrieve the appellate decision. Returns the
    appellate results in input order, each once.
    """
    appellate: list[dict] = []
    seen_urls: set[str] = set()
    for hi, _lo in _appeal_pairs(results):
        if hi["url"] in seen_urls:
            continue
        seen_urls.add(hi["url"])
        appellate.append(hi)
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


# ---------------------------------------------------------------------------
# P3.46: a case the query names that the search did not return
# ---------------------------------------------------------------------------
#
# Batch 12 E's hand-read (P3.22's item 3): in 9 of 25 stored answer-turns an
# answer stated what an authority the National Archives does not hold had
# decided, as if its judgment had been read, and in one of the two sessions
# (FIX_PLAN P3.46) every one of them followed a `search_case_law` call whose
# query named that case and whose results did not include it. Over every
# stored call (1,682 in 70 replay directories), 67 queries name a case and 51
# named cases were not returned (batch 13 E's dry run). The Worker was told nothing about that: the
# window note says how many judgments matched, not that the one it asked for
# by name is absent from them. So the result now says so, in code (P3.7's
# held/absent pattern, Invariant 2).
#
# **What it can say is narrow, and the wording keeps to it.** A case missing
# from one search's results may still exist, may be in the database under
# words the query did not use, or among matching judgments the page did not
# show, and its name or citation may be accurate (P2.4's rule: never question
# the user's citation). So the note says only that THIS search did not return
# it, and what follows for the Worker: nothing of that judgment has been read.
#
# **It errs towards "returned".** A false "not returned" would tell the Worker
# a judgment it holds is absent, which is the Invariant 1 regression. So a
# name counts as returned when any result's title carries a distinctive word
# of EACH party (a party with no distinctive word, "R" or "Secretary of State
# for the Home Department", is not required), and a neutral citation counts
# when any result carries it (as its citation, in its title or in its Find
# Case Law URL). A case named without "v" ("In re Widget"), a name written in
# lower case or capitals throughout, and an anonymised "A v B" are not
# detected at all, so they get no note: the safe direction.
#
# **A law report citation cannot be checked.** Neither database lists judgments
# by law report, so a case named by its report alone ("(1901) AC 9") is never
# said to be missing: its note says the citation cannot be matched to the
# results. A report beside a name or a neutral citation travels with it, and
# the name or the citation decides.
#
# In `[SEARCH SCOPE — …]` form with no square bracket inside (a citation is
# shown in round brackets), so `_TOOL_BLOCK` strips a copy a Worker echoes;
# screened against every detector that reads answers (`test_named_case.py`).

# Neutral-citation courts, England and Wales, the UK, Scotland (P3.20's SCTS
# forms) and Northern Ireland. "SAC (Civ)" before "SAC"; the Court of Appeal's
# and the Sheriff Appeal Court's divisions number separately, so they stay in
# the key, and the High Court's and the tribunals' trailing bracket does not.
_NAMED_NCN_COURTS = (
    r"UKSC|UKHL|UKPC|EWCA\s+(?:Civ|Crim)|EWHC|EWCOP|EWFC|EWCC|EWCR|UKUT|UKFTT|UKEAT|EAT"
    r"|UKAIT|UKIPTrib|UKSIAC|CSOH|CSIH|HCJAC|HCJ|SAC\s*\((?:Civ|Crim)\)|SAC|SC\s+[A-Z]{3,5}"
    r"|UT|NICA|NIQB|NIKB|NICh|NIFam|NICC")
_NAMED_NCN_RX = re.compile(
    r"[\[(]\s*(?P<y>(?:19|20)\d{2})\s*[\])]\s*(?P<court>" + _NAMED_NCN_COURTS + r")\s+"
    r"(?P<num>\d{1,5})\b(?:\s*\((?P<sub>[A-Za-z]{2,10})\))?")
# A Find Case Law URL: court[/division]/year/number.
_NAMED_URL_RX = re.compile(
    r"caselaw\.nationalarchives\.gov\.uk/(?:id/)?(?P<court>[a-z]{2,8})/"
    r"(?:(?P<sub>[a-z]{2,8})/)?(?P<y>(?:19|20)\d{2})/(?P<num>\d{1,5})\b", re.I)
# A law report: a year in brackets, an optional volume, a series of one to
# three capitalised words, a page ("(1901) AC 9", "[1901] 2 All ER 7"); or a
# Scottish series after a bare year ("1901 SLT 7"). Tried after the neutral
# citation, so a court is never read as a series.
_NAMED_REPORT_RX = re.compile(
    r"[\[(]\s*(?:1[5-9]|20)\d{2}\s*[\])]\s*(?:\d{1,3}\s+)?"
    r"[A-Z][A-Za-z.&'’]{0,9}(?:\s+[A-Z][A-Za-z.&'’]{0,9}){0,2}\s+\d{1,5}\b"
    r"|\b(?:1[89]|20)\d{2}\s+(?:SC|SLT|SCLR|JC|SCCR|S\.C\.|S\.L\.T\.)"
    r"(?:\s*\([A-Za-z .]{2,12}\))?\s+\d{1,5}\b")
# Words that join a party's name without being it.
_NAMED_JOINERS = {"of", "the", "and", "&", "for", "on", "in", "at", "de", "la", "le", "du",
                  "van", "von", "der", "da", "application", "ex", "parte", "re"}
# Words that are not a distinctive part of a party's name: the appeal
# detector's list, and the corporate and procedural words.
_NAMED_NOT_DISTINCTIVE = _PARTY_STOPWORDS | {
    "and", "the", "for", "ltd", "limited", "plc", "llp", "inc", "anor", "ors", "others",
    "another", "son", "sons", "application", "parte", "intervener", "interveners",
}
_NAMED_TOKEN_RX = re.compile(r"[\"“”‘’]|[^\s\"“”]+")


def _named_words(text: str) -> set:
    """Distinctive words of a party name, lower-cased: letters only, three or
    more of them, not a generic word, and not a short all-capitals acronym
    ("SSHD", "HMRC"), which a title spells out."""
    out = set()
    for raw in re.findall(r"[A-Za-z][A-Za-z'’]*", text or ""):
        w = raw.replace("'", "").replace("’", "")
        if len(w) < 3 or (w.isupper() and len(w) <= 5):
            continue
        if w.lower() not in _NAMED_NOT_DISTINCTIVE:
            out.add(w.lower())
    return out


def _is_name_token(tok: str) -> bool:
    """A capitalised word or a joiner. A quote (its own token), a citation
    ("[1901]", "(1901)") and a number are none of these, so they end a name."""
    core = tok.strip("(),;:")
    return bool(core) and (core[0].isupper() or core.lower() in _NAMED_JOINERS)


def _side(tokens: list, start: int, step: int, bound: int) -> tuple:
    """(first index, last index) of the party name running from `start` in
    direction `step`, never past `bound`: capitalised words and the joiners
    between them, stopped by a quote, a citation, or any other word. None if
    empty."""
    i, last = start, None
    while 0 <= i < len(tokens) and (i <= bound if step > 0 else i >= bound):
        tok = tokens[i]
        if not _is_name_token(tok):
            break
        # A clause break: a colon or a semicolon ends the first party where
        # it follows a word ("Liability: Widget v ..."), and the second where
        # the word carries it ("Widget v Example: Duty Of Care").
        if step < 0 and tok.rstrip().endswith((":", ";")):
            break
        last = i
        if step > 0 and tok.rstrip().endswith((";", ":")):
            break
        i += step
    if last is None:
        return None
    lo, hi = (start, last) if step > 0 else (last, start)
    # Trim joiners at either end ("of Widget" -> "Widget").
    while lo <= hi and tokens[lo].strip("(),;:").lower() in _NAMED_JOINERS:
        lo += 1
    while hi >= lo and tokens[hi].strip("(),;:").lower() in _NAMED_JOINERS:
        hi -= 1
    return (lo, hi) if lo <= hi else None


def _ncn_key(y: str, court: str, num: str) -> str:
    c = re.sub(r"[^A-Z]", "", court.upper())
    return f"{y} {c} {int(num)}"


def _url_ncn_key(m) -> str:
    court, sub = m.group("court").upper(), (m.group("sub") or "").upper()
    # The Court of Appeal's division is part of its citation; a tribunal's or
    # the High Court's is not.
    return _ncn_key(m.group("y"), court + (sub if court == "EWCA" else ""), m.group("num"))


def _shown(text: str) -> str:
    """A query span as the note shows it: one line, no quotes, round brackets."""
    s = re.sub(r"\s+", " ", text or "").strip().strip("\"“”'‘’ ,;:")
    return s.replace("[", "(").replace("]", ")")[:120].strip()


def named_cases(query: str) -> list:
    """The cases a `search_case_law` query names, in query order:
    `[{"shown", "a", "b", "ncn", "report"}]`. `a` and `b` are the parties'
    distinctive words (an empty set where a party has none: "R"); `ncn` the
    neutral citation's key; `report` True where the case is named by a law
    report alone (it cannot be matched). Never raises."""
    try:
        q = str(query or "")
        cases = []
        cites = []
        for m in _NAMED_NCN_RX.finditer(q):
            cites.append({"start": m.start(), "end": m.end(), "text": m.group(0),
                          "ncn": _ncn_key(m.group("y"), m.group("court"), m.group("num"))})
        for m in _NAMED_REPORT_RX.finditer(q):
            if any(c["start"] <= m.start() < c["end"] or m.start() <= c["start"] < m.end()
                   for c in cites):
                continue
            cites.append({"start": m.start(), "end": m.end(), "text": m.group(0), "ncn": None})
        cites.sort(key=lambda c: c["start"])

        spans = [(m.start(), m.end(), m.group(0)) for m in _NAMED_TOKEN_RX.finditer(q)]
        toks = [t for _, _, t in spans]
        vs = [i for i, tok in enumerate(toks) if tok in ("v", "v.", "vs", "vs.")]
        # Two names in a row ("Widget v Gadget and Gizmo v Sprocket"): the
        # words between their "v"s are split at the last "and" or comma, or,
        # with neither, the second name's first party is its last word.
        bounds = {i: [0, len(toks) - 1] for i in vs}
        for i, j in zip(vs, vs[1:]):
            between = range(i + 1, j)
            cut = next((k for k in reversed(between)
                        if toks[k].lower() in ("and", "&", "or") or toks[k].endswith(",")),
                       None)
            if cut is None:
                bounds[i][1], bounds[j][0] = j - 2, j - 1
            elif toks[cut].endswith(","):
                bounds[i][1], bounds[j][0] = cut, cut + 1
            else:
                bounds[i][1], bounds[j][0] = cut - 1, cut + 1
        for i in vs:
            left = _side(toks, i - 1, -1, bounds[i][0])
            right = _side(toks, i + 1, 1, bounds[i][1])
            if not left or not right:
                continue
            a = _named_words(" ".join(toks[left[0]:left[1] + 1]))
            b = _named_words(" ".join(toks[right[0]:right[1] + 1]))
            # A name with no distinctive word ("R (X) v Secretary of State for
            # ...") cannot be matched; it is kept only to show with a citation
            # that follows it, and dropped below if none does.
            # The name ends before a comma, colon or semicolon its last word
            # carries, so a citation after one is not read as this case's.
            start = spans[left[0]][0]
            end = spans[right[1]][0] + len(toks[right[1]].rstrip(",;:"))
            case = {"start": start, "end": end, "shown": _shown(q[start:end]),
                    "a": a, "b": b, "ncn": None, "report": False}
            # A citation right after the name is that case's (a second one
            # after it, a parallel citation, too).
            attached = False
            for c in cites:
                if not c.get("used") and c["start"] >= end \
                        and not q[end:c["start"]].strip(" ,"):
                    c["used"] = attached = True
                    case["shown"] = _shown(q[start:c["end"]])
                    case["end"] = c["end"]
                    if c["ncn"]:
                        case["ncn"] = c["ncn"]
                    end = c["end"]
            if not a and not b:
                if not attached:
                    continue
                # Named by a law report beside a name that cannot be matched.
                case["report"] = case["ncn"] is None
            cases.append(case)
        for c in cites:
            if c.get("used"):
                continue
            shown = _shown(c["text"])
            cases.append({"start": c["start"], "end": c["end"],
                          "shown": f"the judgment cited as {shown}" if c["ncn"] else shown,
                          "a": set(), "b": set(), "ncn": c["ncn"],
                          "report": c["ncn"] is None})
        cases.sort(key=lambda c: c["start"])
        out, seen = [], set()
        for c in cases:
            k = c["shown"].lower()
            if k in seen:
                continue
            seen.add(k)
            out.append({k2: c[k2] for k2 in ("shown", "a", "b", "ncn", "report")})
        return out
    except Exception:
        return []


def _row_ncn_keys(row: dict) -> set:
    keys = set()
    text = " ".join(str(row.get(f) or "") for f in ("ncn", "title"))
    for m in _NAMED_NCN_RX.finditer(text):
        keys.add(_ncn_key(m.group("y"), m.group("court"), m.group("num")))
    for m in _NAMED_URL_RX.finditer(str(row.get("url") or "")):
        keys.add(_url_ncn_key(m))
    return keys


def _row_title_words(row: dict) -> set:
    return {w.replace("'", "").replace("’", "").lower()
            for w in re.findall(r"[A-Za-z][A-Za-z'’]*", str(row.get("title") or ""))}


def case_returned(case: dict, rows: list) -> Optional[bool]:
    """True when one of `rows` is the named case, False when none is, None
    when it cannot be told (a law report alone). Errs towards True."""
    if case.get("report"):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if case.get("ncn") and case["ncn"] in _row_ncn_keys(row):
            return True
        if case.get("a") or case.get("b"):
            words = _row_title_words(row)
            if (not case["a"] or case["a"] & words) and (not case["b"] or case["b"] & words):
                return True
    return False


def _join(items: list, word: str) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" {word} " + items[-1]


NAMED_CASE_FCL = "Find Case Law"
NAMED_CASE_SCTS = "the Scottish Courts and Tribunals Service's published judgments"
NAMED_CASE_BOTH = f"{NAMED_CASE_FCL} or {NAMED_CASE_SCTS}"


def _not_among(names: list, n: int) -> str:
    """The opening sentence: which named cases the n judgments returned are not."""
    one = len(names) == 1
    if n == 0:
        return ("this search returned 0 judgments, so "
                + ("a case it names is" if one else "the cases it names are")
                + f" not among them: {_join(names, 'and')}.")
    head = ("a case this search names is not among its results" if one else
            "cases this search names are not among its results")
    if n == 1:
        what = (f"is not {names[0]}" if one else
                f"is neither {names[0]} nor {names[1]}" if len(names) == 2 else
                f"is none of {_join(names, 'or')}")
        return f"{head}: the 1 judgment it returned {what}."
    return f"{head}: none of the {n} judgments it returned is {_join(names, 'or')}."


def named_case_note(args: dict, data) -> str:
    """The note on a `search_case_law` result whose query names a case the
    results do not include (P3.46), "" otherwise. Reads Find Case Law's
    `results` and, when the setting is on, `scottish_results`; a list whose
    search did not run (an error, SCTS capped or off) counts for nothing.
    Never raises."""
    try:
        import json as _json
        d = _json.loads(data) if isinstance(data, str) else data
        if not isinstance(d, dict):
            return ""
        cases = named_cases((args or {}).get("query") or d.get("query") or "")
        if not cases:
            return ""
        fcl_ran = not d.get("error")
        block = d.get("scottish") if isinstance(d.get("scottish"), dict) else None
        scts_ran = bool(block) and block.get("status") == "ok"
        if not fcl_ran and not scts_ran:
            return ""
        rows, partial = [], False
        if fcl_ran:
            fcl = d.get("results") if isinstance(d.get("results"), list) else []
            rows += fcl
            partial = partial or (bool(fcl) and not (
                d.get("total_exact") and d.get("total") == len(fcl)))
        if scts_ran:
            scot = (d.get("scottish_results")
                    if isinstance(d.get("scottish_results"), list) else [])
            rows += scot
            partial = partial or (bool(scot) and int(block.get("total") or 0) > len(scot))
        verdicts = [(c, case_returned(c, rows)) for c in cases]
        missing = [c["shown"] for c, v in verdicts if v is False]
        unmatched = [c["shown"] for c, v in verdicts if v is None]
        if not missing and not unmatched:
            return ""
        db = (NAMED_CASE_BOTH if fcl_ran and scts_ran else
              NAMED_CASE_FCL if fcl_ran else NAMED_CASE_SCTS)
        n = len(rows)
        parts = []
        if missing:
            one = len(missing) == 1
            it = "it" if one else "them"
            parts.append(_not_among(missing, n))
            where = (f"{db} may hold {it} among the matching judgments not shown or under "
                     "words this search did not use" if partial else
                     f"{db} may hold {it} under words this search did not use")
            parts.append(
                "That is all it shows: the judgment" + ("" if one else "s")
                + f" may well exist, {where}, and it is no sign that the "
                + ("name or citation is" if one else "names or citations are") + " wrong.")
        if unmatched:
            one = len(unmatched) == 1
            lists = "list" if db == NAMED_CASE_BOTH else "lists"
            parts.append(
                ("This search also names " if missing else "This search names ")
                + ("a law report, " if one else "law reports, ") + _join(unmatched, "and")
                + f", which cannot be matched to its results: {db} {lists} judgments by title "
                  "and neutral citation, not by law report, so none of the judgments returned "
                  "is shown to be " + ("the case reported there." if one else
                                       "a case reported there."))
        several = len(missing) + len(unmatched) > 1
        it, they = ("them", "they") if several else ("it", "it")
        were = "they were" if several else "it was"
        # What the Worker may say of them: "not among" only of a case found
        # missing, "could not be matched" only of a law report.
        say = (f"{were} not among, or could not be matched to," if missing and unmatched else
               f"{were} not among" if missing else
               f"{they} could not be matched to")
        if missing:
            # Scoped to THIS search: another search in the same run may have
            # returned the case and the Worker read it, so the conditional.
            parts.append(
                f"Unless another search returns {it} and you retrieve {it}, "
                + ("their" if several else "its") + " text has not been read: do not state "
                f"what {they} decided as though you had read {it}.")
        else:
            parts.append(
                "Unless a judgment you retrieve proves to be "
                + ("one of those cases" if several else "that case")
                + f", do not state what {they} decided as though you had read {it}.")
        parts.append(
            f"Say instead that {say} the judgments returned, or attribute what you say about "
            f"{it} to a retrieved judgment that cites {it}, and name that judgment.")
        text = " ".join(parts)
        return "\n\n[SEARCH SCOPE — " + text[0].lower() + text[1:] + "]"
    except Exception:
        return ""
