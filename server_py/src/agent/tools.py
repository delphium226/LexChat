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

# -----------------------------------------------------------------------
# Tool schemas (Ollama function-calling format)
# -----------------------------------------------------------------------

MANAGER_TOOLS = []
if settings.enable_deep_research:
    MANAGER_TOOLS.append({
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
    })

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
]


def get_worker_tools(research_mode: str = "legislation_only") -> list:
    """Return the appropriate tool set for the given research mode."""
    if research_mode == "case_law_only":
        return CASE_LAW_TOOLS
    elif research_mode == "legislation_and_case_law":
        return WORKER_TOOLS + CASE_LAW_TOOLS
    return WORKER_TOOLS


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

                payload = {
                    "query": args["query"],
                    "year_from": final_year_from,
                    "year_to": final_year_to,
                    # Over-fetch when jurisdiction filtering so post-filter has enough to work with
                    "limit": 15 if jurisdiction else 5,
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
                # Post-filter by jurisdiction when set, then cap at 5 results.
                if jurisdiction:
                    slimmed["results"] = [
                        r for r in slimmed["results"]
                        if _matches_jurisdiction(r.get("extent", []), jurisdiction)
                    ][:5]
                    slimmed["total"] = len(slimmed["results"])
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

            else:
                return f"Error: Tool {name} not found in worker toolset."

    except httpx.HTTPStatusError as e:
        logger.error(f"[Tool Error] {name}: {e.response.text}")
        return f"Error executing tool: {e.response.text}"
    except Exception as e:
        logger.error(f"[Tool Error] {name}: {e}")
        return f"Error executing tool: {str(e)}"
