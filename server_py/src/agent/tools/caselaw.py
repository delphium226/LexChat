"""National Archives case law: Atom feed and LegalDocML (AKN) judgment parsing."""

import re
import xml.etree.ElementTree as ET

import httpx


_ATOM_NS = "http://www.w3.org/2005/Atom"
_UK_NS = "https://caselaw.nationalarchives.gov.uk/terms/v1"


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


def _court_rank(ncn: str, court: str) -> int:
    """Return the court-hierarchy rank for a result from its NCN/court fields (0 = unknown)."""
    text = f"{ncn} {court}".upper()
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
            "rank": _court_rank(r.get("ncn", ""), r.get("court", "")),
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
        ncn = entry.findtext(f"{{{_UK_NS}}}ncn", "")
        court = entry.findtext(f"{{{_UK_NS}}}court", "")
        entries.append({
            "title": title,
            "ncn": ncn,
            "court": court,
            "date": published[:10] if published else "",
            "url": url,
        })
    return entries


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


async def _fetch_judgment_text(url: str) -> dict:
    """Fetch and return the full text of a National Archives judgment via its data.xml URL."""
    data_url = url.rstrip("/") + "/data.xml"
    async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
        resp = await client.get(data_url)
        resp.raise_for_status()
    text = _extract_judgment_text(resp.text)
    # Extract title and NCN from the Atom entry we already have (best effort from XML)
    try:
        root = ET.fromstring(resp.text)
        ncn = root.findtext(f"{{{_UK_NS}}}ncn") or ""
        title_el = root.find(".//{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}FRBRname")
        title = title_el.get("value", "") if title_el is not None else ""
    except Exception:
        ncn = ""
        title = ""
    return {"url": url, "title": title, "ncn": ncn, "text": text}

