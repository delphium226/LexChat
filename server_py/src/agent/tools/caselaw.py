"""National Archives case law: Atom feed and LegalDocML (AKN) judgment parsing."""

import xml.etree.ElementTree as ET

import httpx


_ATOM_NS = "http://www.w3.org/2005/Atom"
_UK_NS = "https://caselaw.nationalarchives.gov.uk/terms/v1"


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

