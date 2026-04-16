import asyncio
from typing import Optional, Callable
from urllib.parse import urlparse
import json
import logging
import time
import uuid

import httpx

from ..config import settings

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
                payload = {
                    "query": args["query"],
                    "year_from": args.get("year_from"),
                    "year_to": args.get("year_to"),
                    "limit": 5,
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
                # Slim the response before returning — strips provenance metadata,
                # timestamps, and ranked section arrays the model never uses.
                # Reduces a typical 5-result payload from ~10k to ~1.5k chars,
                # keeping it under the summarisation threshold.
                return json.dumps(_slim_search_results(resp_json))

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

            else:
                return f"Error: Tool {name} not found in worker toolset."

    except httpx.HTTPStatusError as e:
        logger.error(f"[Tool Error] {name}: {e.response.text}")
        return f"Error executing tool: {e.response.text}"
    except Exception as e:
        logger.error(f"[Tool Error] {name}: {e}")
        return f"Error executing tool: {str(e)}"
