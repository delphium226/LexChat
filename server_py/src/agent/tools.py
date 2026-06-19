import asyncio
from typing import Optional, Callable
from urllib.parse import urlparse
import json
import logging
import time
import uuid
import xml.etree.ElementTree as ET

import httpx

from ..config import settings
from .provider_factory import get_request_provider_config

logger = logging.getLogger("agent")


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

# -----------------------------------------------------------------------
# Tool schemas (Ollama function-calling format)
# -----------------------------------------------------------------------

MANAGER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "delegate_research",
            "description": (
                "Delegates a legal research task to a specialized agent that searches the UK legislation database. "
                "Use this for any question about UK Acts or Statutory Instruments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "A self-contained research brief for the agent. "
                            "The agent has no access to the conversation history, so this must include: "
                            "(1) the precise legal question; "
                            "(2) any specific Act names, SI numbers, or years mentioned in the conversation; "
                            "(3) any jurisdiction constraints (e.g. England and Wales, Scotland); "
                            "(4) relevant context from prior turns that would help narrow the search. "
                            "Do not forward the user's raw message if additional context exists."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
]

def get_manager_tools(peer_descriptions: str = "") -> list:
    """Return the manager tool list, optionally including consult_peer.

    When peer_descriptions is empty the output is identical to MANAGER_TOOLS so
    existing behaviour is completely unchanged for deployments with no peers.
    """
    tools = list(MANAGER_TOOLS)
    if peer_descriptions:
        tools.append({
            "type": "function",
            "function": {
                "name": "consult_peer",
                "description": (
                    f"Consult a peer bot for specialised knowledge. "
                    f"Available peers:\n{peer_descriptions}"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "peer_id": {
                            "type": "string",
                            "description": "peer_id of the bot to consult",
                        },
                        "question": {
                            "type": "string",
                            "description": "The specific question to ask the peer",
                        },
                    },
                    "required": ["peer_id", "question"],
                },
            },
        })
    return tools


WORKER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_legislation",
            "description": "Search for UK legislation (Acts and Statutory Instruments) by title or content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": 'The search query (e.g., "Computer Misuse Act", "speeding fines").',
                    },
                    "year_from": {
                        "type": "integer",
                        "description": "Optional start year filter.",
                    },
                    "year_to": {
                        "type": "integer",
                        "description": "Optional end year filter.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_legislation_sections",
            "description": (
                "Search for specific sections within a known piece of legislation. "
                "Use this INSTEAD of get_legislation_text when you already have a legislation_id "
                "and need to find particular provisions, definitions, or duties within it. "
                "Returns only the matching sections — avoids downloading the entire Act."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The provision or topic to search for within the Act (e.g. \"public sector equality duty\", \"penalty\", \"definition of employee\").",
                    },
                    "legislation_id": {
                        "type": "string",
                        "description": "The legislation ID to search within (e.g. \"ukpga/2010/15\"). Must be obtained from a prior search_legislation call.",
                    },
                },
                "required": ["query", "legislation_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_legislation_text",
            "description": (
                "Get the FULL text of a piece of legislation. "
                "Only use this when search_legislation_sections returns insufficient results, "
                "or when the question requires understanding the overall structure of the Act. "
                "For targeted questions about specific provisions, prefer search_legislation_sections."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "legislation_id": {
                        "type": "string",
                        "description": 'The legislation ID (e.g., "ukpga/1990/18"). Must be obtained from a prior search_legislation call.',
                    },
                },
                "required": ["legislation_id"],
            },
        },
    },
]


CASE_LAW_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_case_law",
            "description": (
                "Search for UK case law judgments from the National Archives Find Case Law database. "
                "Returns judgment titles, neutral citation numbers (NCNs), courts, dates, and URLs. "
                "Use this to find leading cases, precedents, and judicial decisions on a legal topic. "
                "DATABASE COVERAGE: Primarily covers England & Wales courts and UK-wide courts. "
                "The Scottish Court of Session (CSOH/CSIH) and Sheriff Courts are NOT indexed. "
                "For Scottish matters, this database contains only UK Supreme Court and Privy Council decisions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (e.g., 'fair dismissal reasonable adjustment', 'judicial review planning permission').",
                    },
                    "court": {
                        "type": "string",
                        "description": (
                            "Optional court filter. ONLY use one of these exact values: "
                            "'uksc' (UK Supreme Court), 'ukpc' (Privy Council), "
                            "'ewca/civ' (Court of Appeal Civil), 'ewca/crim' (Court of Appeal Criminal), "
                            "'ewhc/admin' (Administrative Court), 'ewhc/qb' (King's Bench), "
                            "'ewhc/ch' (Chancery), 'ewhc/fam' (Family), 'ewhc/comm' (Commercial), "
                            "'ewhc/pat' (Patents), 'ewhc/tcc' (Technology & Construction), "
                            "'ukut' (Upper Tribunal), 'ukut/iac' (Immigration), 'ukut/lc' (Lands Chamber), "
                            "'eat' (Employment Appeal Tribunal). "
                            "DO NOT invent court codes — an invalid value causes a 400 error. Omit to search all courts."
                        ),
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Optional start date filter (YYYY-MM-DD).",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Optional end date filter (YYYY-MM-DD).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_case_law_text",
            "description": (
                "Retrieve the full text of a specific judgment from the National Archives Find Case Law database. "
                "Use a URL returned by search_case_law. "
                "Returns the complete judgment text so you can read the reasoning, holdings, and obiter dicta "
                "before synthesising your answer. Call this for the 1–3 most relevant cases found in Phase 1."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the case exactly as returned by search_case_law (e.g. 'https://caselaw.nationalarchives.gov.uk/uksc/2023/1').",
                    },
                },
                "required": ["url"],
            },
        },
    },
]


PARLIAMENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_hansard",
            "description": (
                "Search UK Parliament Hansard for speeches, debates, and written questions. "
                "Returns speech excerpts with speaker, date, debate title, and a gid (global ID). "
                "Follow up with get_hansard_debate to retrieve the full text of a relevant speech."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Full-text search query (e.g., 'housing supply planning', 'immigration Rwanda policy').",
                    },
                    "debate_type": {
                        "type": "string",
                        "description": (
                            "Optional type filter. One of: 'debates' (Commons chamber), "
                            "'lords' (Lords chamber), 'wrans' (written answers), "
                            "'wms' (written ministerial statements). Omit to search all types."
                        ),
                    },
                    "speaker": {
                        "type": "string",
                        "description": "Optional: filter results to a specific speaker by name.",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Optional start date filter (YYYY-MM-DD).",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Optional end date filter (YYYY-MM-DD).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hansard_debate",
            "description": (
                "Retrieve the full text of a specific Hansard debate or speech using a gid returned by search_hansard. "
                "Use this after search_hansard when an excerpt is directly relevant but truncated."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "gid": {
                        "type": "string",
                        "description": "The global ID (gid) of the debate or speech, as returned by search_hansard.",
                    },
                    "debate_type": {
                        "type": "string",
                        "description": (
                            "The type of content this gid refers to: 'debates' (Commons), "
                            "'lords', or 'wrans' (written answers). Defaults to 'debates' if omitted."
                        ),
                    },
                },
                "required": ["gid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_member_info",
            "description": (
                "Look up information about a UK Parliament member (MP or Lord) or Scottish Parliament MSP. "
                "Returns biography, party, constituency, and current roles."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The member's name (e.g., 'Keir Starmer', 'Angela Rayner').",
                    },
                    "parliament": {
                        "type": "string",
                        "description": "Which parliament to search: 'commons' (default), 'lords', or 'scotland'.",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_bills",
            "description": (
                "Search for parliamentary bills by topic, title, or keyword. "
                "Returns bill title, current stage, house, and a link to the bill page."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term (e.g., 'Renters Rights Bill', 'planning reform').",
                    },
                    "parliament": {
                        "type": "string",
                        "description": "Which parliament: 'uk' (Westminster, default) or 'scotland' (Holyrood).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_scottish_parliament",
            "description": (
                "Search Scottish Parliament (Holyrood) debates and written answers. "
                "Returns speech excerpts from MSPs with speaker, date, and gid."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Full-text search query.",
                    },
                    "debate_type": {
                        "type": "string",
                        "description": "Type of content: 'debates' (chamber debates) or 'written_answers'. Omit to search all.",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Optional start date filter (YYYY-MM-DD).",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Optional end date filter (YYYY-MM-DD).",
                    },
                },
                "required": ["query"],
            },
        },
    },
]

_PARLIAMENT_TOOL_NAMES = {t["function"]["name"] for t in PARLIAMENT_TOOLS}


def get_worker_tools(research_mode: str = "legislation_only") -> list:
    """Return the appropriate tool set for the given research mode."""
    if research_mode == "case_law_only":
        return CASE_LAW_TOOLS
    elif research_mode == "legislation_and_case_law":
        return WORKER_TOOLS + CASE_LAW_TOOLS
    elif research_mode == "parliamentary_records":
        return PARLIAMENT_TOOLS
    return WORKER_TOOLS


import re as _re

_TWFY_API_BASE = "https://www.theyworkforyou.com/api"


def _strip_html(text: str) -> str:
    import html as _html
    clean = _re.sub(r"<[^>]+>", " ", text or "")
    return _html.unescape(clean).strip()


def _slim_hansard_results(resp, query: str, source_type: str = "hansard") -> dict:
    """Slim a TheyWorkForYou getHansard response to the fields the model needs.

    source_type: "hansard" for UK Parliament results, "scottish_parliament" for SP results.
    Passed explicitly because SP listurls don't match the UK listurl patterns and would
    otherwise fall back to debate_type "debates" (the UK Commons endpoint), causing
    get_hansard_debate to call the wrong TWFY endpoint.
    """
    if isinstance(resp, dict) and "error" in resp:
        return {"error": resp["error"], "results": [], "total": 0, "query": query}
    rows = resp if isinstance(resp, list) else resp.get("rows", [])
    slimmed = []
    for speech in rows[:10]:
        body_clean = _strip_html(speech.get("body", ""))
        speaker = speech.get("speaker") or {}
        speaker_name = (
            speaker.get("name", "") if isinstance(speaker, dict) else ""
        ) or speech.get("hname", "")

        # Debate title: TWFY API puts this in parent.body, not debate.name
        parent = speech.get("parent") or {}
        parent_body = parent.get("body", "") if isinstance(parent, dict) else ""
        debate_name = _strip_html(parent_body) if parent_body else ""

        listurl = speech.get("listurl", "")
        if source_type == "scottish_parliament":
            # SP written answers use spwrans; all other SP content uses getSP
            debate_type_hint = "spwrans" if "wrans" in listurl.lower() else "sp"
        elif "/lords/" in listurl:
            debate_type_hint = "lords"
        elif "/wrans/" in listurl:
            debate_type_hint = "wrans"
        elif "/wms/" in listurl:
            debate_type_hint = "wms"
        else:
            debate_type_hint = "debates"

        gid = speech.get("gid", "")
        if source_type == "scottish_parliament":
            speech_url = f"https://www.theyworkforyou.com/sp/?id={gid}"
        else:
            speech_url = f"https://www.theyworkforyou.com/debate/?id={gid}"
        slimmed.append({
            "gid": gid,
            "hdate": speech.get("hdate", ""),
            "speaker": speaker_name,
            "debate": debate_name,
            "debate_type": debate_type_hint,
            "excerpt": body_clean[:400],
            "url": speech_url,
        })
    return {"results": slimmed, "total": len(slimmed), "query": query}


def _slim_members_results(resp: dict) -> dict:
    """Slim a UK Parliament Members API response."""
    items = resp.get("items", [])
    slimmed = []
    for item in items[:5]:
        v = item.get("value", {})
        membership = v.get("latestHouseMembership", {}) or {}
        slimmed.append({
            "id": v.get("id"),
            "name": v.get("nameDisplayAs", ""),
            "party": (v.get("latestParty") or {}).get("name", ""),
            "constituency": membership.get("membershipFrom", ""),
            "house": membership.get("house", ""),
            "url": f"https://members.parliament.uk/member/{v.get('id')}/contact",
        })
    return {"results": slimmed, "total": resp.get("totalResults", len(slimmed))}


def _slim_bills_results(resp: dict) -> dict:
    """Slim a UK Parliament Bills API response."""
    items = resp.get("items", [])
    slimmed = []
    for item in items[:10]:
        stage = item.get("currentStage") or {}
        slimmed.append({
            "billId": item.get("billId"),
            "shortTitle": item.get("shortTitle", ""),
            "currentStage": stage.get("description", "") if isinstance(stage, dict) else str(stage),
            "currentHouse": item.get("currentHouse", ""),
            "lastUpdate": item.get("lastUpdate", ""),
            "url": f"https://bills.parliament.uk/bills/{item.get('billId')}",
        })
    return {"results": slimmed, "total": resp.get("totalResults", len(slimmed))}


async def execute_parliament_tool(
    name: str,
    args: dict,
    on_chunk: Optional[Callable] = None,
    timing_collector=None,
) -> str:
    """Execute a parliament research tool call and return JSON string result."""
    logger.info(f"[Parliament Tool Exec] {name} with args: {json.dumps(args)}")

    call_id = str(uuid.uuid4())
    twfy_key = settings.twfy_api_key or ""

    if not twfy_key and name in {"search_hansard", "get_hansard_debate", "search_scottish_parliament"}:
        return json.dumps({
            "error": (
                "TWFY_API_KEY is not configured. "
                "Register for a free key at https://www.theyworkforyou.com/api/key "
                "and add TWFY_API_KEY to your environment."
            ),
            "results": [],
        })

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:

            if name == "search_hansard":
                url = f"{_TWFY_API_BASE}/getHansard"
                params: dict = {
                    "key": twfy_key,
                    "output": "js",
                    "search": args["query"],
                    "num": 10,
                }
                if args.get("debate_type"):
                    params["type"] = args["debate_type"]
                if args.get("speaker"):
                    params["person"] = args["speaker"]
                # Note: TWFY getHansard does not support date range filtering.
                # date_from/date_to are accepted by the tool schema for intent
                # but are not forwarded to the API — results are ordered by date
                # (most recent first) regardless of any date constraints.

                await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url, "method": "GET", "payload": params})
                t0 = time.perf_counter()
                resp = await client.get(url, params=params)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)
                try:
                    resp_json = resp.json()
                except Exception:
                    resp_json = {"text": resp.text}
                await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url, "status": resp.status_code, "response": resp_json, "elapsed_ms": round(elapsed_ms)})
                resp.raise_for_status()
                return json.dumps(_slim_hansard_results(resp_json, args["query"]))

            elif name == "get_hansard_debate":
                gid = args["gid"]
                debate_type = args.get("debate_type", "debates")
                gid_lower = gid.lower()
                if "wrans" in gid_lower or debate_type == "wrans":
                    endpoint = "getWrans"
                elif "lords" in gid_lower or debate_type == "lords":
                    endpoint = "getLords"
                elif debate_type in ("sp", "spwrans"):
                    # Scottish Parliament debates and written answers both use getSP in TWFY
                    endpoint = "getSP"
                else:
                    endpoint = "getDebates"

                url = f"{_TWFY_API_BASE}/{endpoint}"
                params = {"key": twfy_key, "output": "js", "id": gid}

                await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url, "method": "GET", "payload": params})
                t0 = time.perf_counter()
                resp = await client.get(url, params=params)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)
                try:
                    resp_json = resp.json()
                except Exception:
                    resp_json = {"text": resp.text}
                await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url, "status": resp.status_code, "response": {"preview": str(resp_json)[:300]}, "elapsed_ms": round(elapsed_ms)})
                resp.raise_for_status()
                return json.dumps(resp_json)

            elif name == "get_member_info":
                parliament = args.get("parliament", "commons")

                if parliament == "scotland":
                    url = f"{_TWFY_API_BASE}/getMSPInfo"
                    params = {"key": twfy_key, "output": "js", "search": args["name"]}
                    await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url, "method": "GET", "payload": params})
                    t0 = time.perf_counter()
                    resp = await client.get(url, params=params)
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    if timing_collector:
                        timing_collector.record_lex_api_call(name, elapsed_ms)
                    try:
                        resp_json = resp.json()
                    except Exception:
                        resp_json = {"text": resp.text}
                    await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url, "status": resp.status_code, "response": resp_json, "elapsed_ms": round(elapsed_ms)})
                    resp.raise_for_status()
                    return json.dumps(resp_json)

                else:
                    house = 2 if parliament == "lords" else 1
                    url = "https://members-api.parliament.uk/api/Members/Search"
                    params = {"Name": args["name"], "House": house, "IsCurrentMember": "false", "Skip": 0, "Take": 5}
                    await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url, "method": "GET", "payload": params})
                    t0 = time.perf_counter()
                    resp = await client.get(url, params=params)
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    if timing_collector:
                        timing_collector.record_lex_api_call(name, elapsed_ms)
                    try:
                        resp_json = resp.json()
                    except Exception:
                        resp_json = {"text": resp.text}
                    await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url, "status": resp.status_code, "response": resp_json, "elapsed_ms": round(elapsed_ms)})
                    resp.raise_for_status()
                    return json.dumps(_slim_members_results(resp_json))

            elif name == "search_bills":
                parliament = args.get("parliament", "uk")

                if parliament == "scotland":
                    url = "https://data.parliament.scot/api/bills"
                    params = {}
                    await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url, "method": "GET", "payload": params})
                    t0 = time.perf_counter()
                    resp = await client.get(url, params=params)
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    if timing_collector:
                        timing_collector.record_lex_api_call(name, elapsed_ms)
                    try:
                        resp_json = resp.json()
                    except Exception:
                        resp_json = {"text": resp.text}
                    await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url, "status": resp.status_code, "response": resp_json, "elapsed_ms": round(elapsed_ms)})
                    resp.raise_for_status()
                    # Filter Scottish bills by query keyword (no server-side search param)
                    query_lower = args["query"].lower()
                    bills = resp_json if isinstance(resp_json, list) else resp_json.get("items", [])
                    filtered = [
                        b for b in bills
                        if query_lower in (b.get("ShortTitle") or b.get("title") or "").lower()
                        or query_lower in (b.get("LongTitle") or "").lower()
                    ][:10]
                    slimmed = [{
                        "billId": b.get("BillId") or b.get("id"),
                        "shortTitle": b.get("ShortTitle") or b.get("title", ""),
                        "currentStage": b.get("CurrentStage") or b.get("stage", ""),
                        "url": f"https://www.parliament.scot/bills-and-laws/bills/{b.get('BillId') or b.get('id')}",
                    } for b in filtered]
                    return json.dumps({"results": slimmed, "total": len(slimmed), "parliament": "scotland"})

                else:
                    url = "https://bills-api.parliament.uk/api/v1/Bills"
                    params = {"SearchTerm": args["query"], "SortOrder": "DateUpdatedDescending", "Take": 10, "Skip": 0}
                    await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url, "method": "GET", "payload": params})
                    t0 = time.perf_counter()
                    resp = await client.get(url, params=params)
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    if timing_collector:
                        timing_collector.record_lex_api_call(name, elapsed_ms)
                    try:
                        resp_json = resp.json()
                    except Exception:
                        resp_json = {"text": resp.text}
                    await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url, "status": resp.status_code, "response": resp_json, "elapsed_ms": round(elapsed_ms)})
                    resp.raise_for_status()
                    return json.dumps(_slim_bills_results(resp_json))

            elif name == "search_scottish_parliament":
                url = f"{_TWFY_API_BASE}/getHansard"
                debate_type = args.get("debate_type")
                twfy_type = "spwrans" if debate_type == "written_answers" else "sp"
                params = {
                    "key": twfy_key,
                    "output": "js",
                    "search": args["query"],
                    "type": twfy_type,
                    "num": 10,
                }
                # TWFY getHansard does not support date range filtering — params ignored.

                await _emit(on_chunk, {"type": "api_call_start", "id": call_id, "url": url, "method": "GET", "payload": params})
                t0 = time.perf_counter()
                resp = await client.get(url, params=params)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)
                try:
                    resp_json = resp.json()
                except Exception:
                    resp_json = {"text": resp.text}
                await _emit(on_chunk, {"type": "api_call_end", "id": call_id, "url": url, "status": resp.status_code, "response": resp_json, "elapsed_ms": round(elapsed_ms)})
                resp.raise_for_status()
                return json.dumps(_slim_hansard_results(resp_json, args["query"], source_type="scottish_parliament"))

            else:
                return f"Error: Tool {name} not found in parliament toolset."

    except httpx.HTTPStatusError as e:
        logger.error(f"[Parliament Tool Error] {name}: {e.response.text}")
        return f"Error executing tool: {e.response.text}"
    except Exception as e:
        logger.error(f"[Parliament Tool Error] {name}: {e}")
        return f"Error executing tool: {str(e)}"


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


# -----------------------------------------------------------------------
# Tool execution (LEX API client)
# -----------------------------------------------------------------------

async def _emit(on_chunk: Optional[Callable], data: dict):
    """Helper to emit events if callback is provided."""
    if on_chunk:
        res = on_chunk(data)
        if asyncio.iscoroutine(res):
            await res

async def execute_worker_tool(
    name: str,
    args: dict,
    on_chunk: Optional[Callable] = None,
    timing_collector=None,
) -> str:
    """Execute a worker tool (LEX API call) and return JSON string result."""
    logger.info(f"[Worker Tool Exec] {name} with args: {json.dumps(args)}")

    call_id = str(uuid.uuid4())

    try:
        # Disable SSL verification to support internal deployments with self-signed certs or SSL inspection
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            if name == "search_legislation":
                url = f"{LEX_API_URL}/legislation/search"
                cfg = get_request_provider_config()
                user_year_from = cfg.get("_year_from")
                user_year_to = cfg.get("_year_to")
                jurisdiction = cfg.get("_jurisdiction")
                legislation_type = cfg.get("_legislation_type")
                current_only = cfg.get("_current_only", False)

                # Merge user filter with model-supplied year args (take intersection)
                model_year_from = args.get("year_from")
                model_year_to = args.get("year_to")
                if user_year_from and model_year_from:
                    final_year_from = max(user_year_from, model_year_from)
                else:
                    final_year_from = user_year_from or model_year_from
                if user_year_to and model_year_to:
                    final_year_to = min(user_year_to, model_year_to)
                else:
                    final_year_to = user_year_to or model_year_to

                needs_post_filter = bool(jurisdiction or legislation_type or current_only)
                payload = {
                    "query": args["query"],
                    "year_from": final_year_from,
                    "year_to": final_year_to,
                    # Over-fetch when post-filters are active so they have enough results to work with
                    "limit": 20 if needs_post_filter else 5,
                    "include_text": False,
                }

                await _emit(on_chunk, {
                    "type": "api_call_start",
                    "id": call_id,
                    "url": url,
                    "method": "POST",
                    "payload": payload
                })

                t0 = time.perf_counter()
                resp = await client.post(url, json=payload)
                elapsed_ms = (time.perf_counter() - t0) * 1000

                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)

                # Emit result before raising error, to see what happened
                try:
                    resp_json = resp.json()
                except:
                    resp_json = {"text": resp.text}

                await _emit(on_chunk, {
                    "type": "api_call_end",
                    "id": call_id,
                    "url": url,
                    "status": resp.status_code,
                    "response": resp_json,
                    "elapsed_ms": round(elapsed_ms),
                })

                resp.raise_for_status()
                slimmed = _slim_search_results(resp_json)
                results = slimmed["results"]

                # Post-filter: legislation type (by legislation_id prefix)
                if legislation_type:
                    type_codes = _TYPE_CODES.get(legislation_type, set())
                    results = [
                        r for r in results
                        if r.get("legislation_id", "").split("/")[0] in type_codes
                    ]

                # Post-filter: current legislation only (exclude known non-in-force)
                if current_only:
                    _INACTIVE = {"repealed", "revoked", "spent", "expired", "not in force"}
                    results = [
                        r for r in results
                        if r.get("status", "").lower() not in _INACTIVE
                    ]

                # Post-filter: jurisdiction (by extent field)
                if jurisdiction:
                    results = [
                        r for r in results
                        if _matches_jurisdiction(r.get("extent", []), jurisdiction)
                    ]

                results = results[:5]
                slimmed["results"] = results
                slimmed["total"] = len(results)
                return json.dumps(slimmed)

            elif name == "search_legislation_sections":
                url = f"{LEX_API_URL}/legislation/section/search"
                payload = {
                    "query": args["query"],
                    "legislation_id": args["legislation_id"],
                    "limit": 10,
                }

                await _emit(on_chunk, {
                    "type": "api_call_start",
                    "id": call_id,
                    "url": url,
                    "method": "POST",
                    "payload": payload,
                })

                t0 = time.perf_counter()
                resp = await client.post(url, json=payload)
                elapsed_ms = (time.perf_counter() - t0) * 1000

                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)

                try:
                    resp_json = resp.json()
                except Exception:
                    resp_json = {"text": resp.text}

                await _emit(on_chunk, {
                    "type": "api_call_end",
                    "id": call_id,
                    "url": url,
                    "status": resp.status_code,
                    "response": resp_json,
                    "elapsed_ms": round(elapsed_ms),
                })

                resp.raise_for_status()
                return json.dumps(resp_json)

            elif name == "get_legislation_text":
                url = f"{LEX_API_URL}/legislation/text"
                payload = {"legislation_id": args["legislation_id"]}

                await _emit(on_chunk, {
                    "type": "api_call_start",
                    "id": call_id,
                    "url": url,
                    "method": "POST",
                    "payload": payload
                })

                t0 = time.perf_counter()
                resp = await client.post(url, json=payload)
                elapsed_ms = (time.perf_counter() - t0) * 1000

                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)

                try:
                    resp_json = resp.json()
                except:
                    resp_json = {"text": resp.text}

                await _emit(on_chunk, {
                    "type": "api_call_end",
                    "id": call_id,
                    "url": url,
                    "status": resp.status_code,
                    "response": resp_json,
                    "elapsed_ms": round(elapsed_ms),
                })

                resp.raise_for_status()
                return json.dumps(resp_json)

            elif name == "search_case_law":
                url = "https://caselaw.nationalarchives.gov.uk/atom.xml"
                params: dict = {"query": args["query"]}
                if args.get("court"):
                    params["court"] = args["court"]
                if args.get("date_from"):
                    params["date_from"] = args["date_from"]
                if args.get("date_to"):
                    params["date_to"] = args["date_to"]

                # Apply user's hard filter constraints (override model args)
                cl_cfg = get_request_provider_config()
                if cl_cfg.get("_court"):
                    params["court"] = cl_cfg["_court"]
                if cl_cfg.get("_date_from"):
                    model_df = args.get("date_from") or ""
                    params["date_from"] = max(model_df, cl_cfg["_date_from"]) if model_df else cl_cfg["_date_from"]
                if cl_cfg.get("_date_to"):
                    model_dt = args.get("date_to") or ""
                    params["date_to"] = min(model_dt, cl_cfg["_date_to"]) if model_dt else cl_cfg["_date_to"]

                await _emit(on_chunk, {
                    "type": "api_call_start",
                    "id": call_id,
                    "url": url,
                    "method": "GET",
                    "payload": params,
                })

                t0 = time.perf_counter()
                resp = await client.get(url, params=params, timeout=15.0)
                elapsed_ms = (time.perf_counter() - t0) * 1000

                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)

                await _emit(on_chunk, {
                    "type": "api_call_end",
                    "id": call_id,
                    "url": url,
                    "status": resp.status_code,
                    "response": {"preview": resp.text[:300]},
                    "elapsed_ms": round(elapsed_ms),
                })

                if resp.status_code == 400:
                    court = args.get("court", "")
                    return json.dumps({
                        "error": f"Invalid court filter '{court}'. Use only the exact court codes listed in the tool description (e.g. 'uksc', 'ewca/civ', 'ewhc/admin'). Retry without the court filter, or with a valid code.",
                        "results": [],
                        "total": 0,
                    })
                resp.raise_for_status()
                entries = _parse_case_law_atom(resp.text)
                return json.dumps({
                    "results": entries,
                    "total": len(entries),
                    "query": args["query"],
                })

            elif name == "get_case_law_text":
                url = args["url"]

                await _emit(on_chunk, {
                    "type": "api_call_start",
                    "id": call_id,
                    "url": url + "/data.xml",
                    "method": "GET",
                    "payload": {},
                })

                t0 = time.perf_counter()
                try:
                    result = await _fetch_judgment_text(url)
                except httpx.HTTPStatusError as e:
                    result = {"error": f"HTTP {e.response.status_code} fetching judgment", "url": url, "text": ""}
                except Exception as e:
                    result = {"error": str(e), "url": url, "text": ""}
                elapsed_ms = (time.perf_counter() - t0) * 1000

                if timing_collector:
                    timing_collector.record_lex_api_call(name, elapsed_ms)

                await _emit(on_chunk, {
                    "type": "api_call_end",
                    "id": call_id,
                    "url": url + "/data.xml",
                    "status": 200 if "text" in result and result["text"] else 0,
                    "response": {"preview": result.get("text", "")[:300]},
                    "elapsed_ms": round(elapsed_ms),
                })

                return json.dumps(result)

            else:
                return f"Error: Tool {name} not found in worker toolset."

    except httpx.HTTPStatusError as e:
        logger.error(f"[Tool Error] {name}: {e.response.text}")
        return f"Error executing tool: {e.response.text}"
    except Exception as e:
        logger.error(f"[Tool Error] {name}: {e}")
        return f"Error executing tool: {str(e)}"
