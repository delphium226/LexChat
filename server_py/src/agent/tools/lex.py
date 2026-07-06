"""LEX API result slimming and legislation-search helpers."""

from urllib.parse import urlparse

from ...config import settings


def _slim_search_results(resp_json: dict) -> dict:
    """Strip the search_legislation response down to only the fields the model needs.

    The raw API response includes provenance metadata, timestamps, descriptions,
    and a ranked sections array that the model never uses. Stripping these keeps
    a typical 5-result payload well under the summarisation threshold (~1-2k chars)
    and gives the model a clean, readable result.

    description is intentionally excluded — it is verbose and redundant once Phase 2
    retrieves actual section text via search_legislation_sections.

    legislation_id is derived from the URI and included explicitly so the model
    can pass it directly to search_legislation_sections.
    """
    slimmed = []
    for item in resp_json.get("results", []):
        uri = item.get("uri", "")
        legislation_id = urlparse(uri).path.lstrip("/") if uri else ""
        # Some API responses include /id/ in the URI path — strip it so the
        # legislation_id can be passed directly to search_legislation_sections.
        if legislation_id.startswith("id/"):
            legislation_id = legislation_id[3:]
        slimmed.append({
            "legislation_id": legislation_id,
            "title": item.get("title", ""),
            "url": uri,
            "status": item.get("status", ""),
            "year": item.get("year"),
            "extent": item.get("extent", []),
        })
    return {
        "results": slimmed,
        "total": resp_json.get("total", len(slimmed)),
    }


def _matches_jurisdiction(extent: list, jurisdiction: str) -> bool:
    """Return True if the legislation extent covers the requested jurisdiction.

    Extent values are strings like "E+W+S+NI". Split on "+" to get individual
    territory tokens: E (England), W (Wales), S (Scotland), NI (Northern Ireland).
    An empty extent list is treated as unknown — included by default.
    """
    if not extent:
        return True
    tokens: set[str] = set()
    for e in extent:
        for t in e.split("+"):
            tokens.add(t.strip())
    if jurisdiction == "england_and_wales":
        return "E" in tokens
    if jurisdiction == "scotland":
        return "S" in tokens
    if jurisdiction == "northern_ireland":
        return "NI" in tokens
    if jurisdiction == "wales":
        return "W" in tokens
    if jurisdiction == "uk_wide":
        return tokens >= {"E", "W", "S", "NI"}
    return True


def extract_legislation_ids_from_search(resp_json: dict) -> list[tuple[str, str]]:
    """Extract (legislation_id, title) pairs from a slimmed search_legislation response."""
    return [
        (item["legislation_id"], item.get("title", ""))
        for item in resp_json.get("results", [])
        if item.get("legislation_id")
    ]

LEX_API_URL = settings.lex_api_url.rstrip("/")

_TYPE_CODES: dict[str, set[str]] = {
    "primary":   {"ukpga", "ukppa", "ukla", "asp", "nia"},
    "secondary": {"uksi", "ssi", "wsi", "nisr"},
    "draft":     {"ukdsi"},
}
