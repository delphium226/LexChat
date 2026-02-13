import asyncio
from typing import Optional, Callable
import json
import logging

import httpx

from ..config import settings

logger = logging.getLogger("agent")

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
                "Delegates a complex legal research task to a specialized agent. "
                "Use this for any question about UK legislation, case law, or legal concepts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The detailed research question to ask the specialized agent.",
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
            "name": "get_legislation_text",
            "description": "Get the full text of a specific piece of legislation using its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "legislation_id": {
                        "type": "string",
                        "description": 'The legislation ID (e.g., "ukpga/1990/18").',
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

async def execute_worker_tool(name: str, args: dict, on_chunk: Optional[Callable] = None) -> str:
    """Execute a worker tool (LEX API call) and return JSON string result."""
    logger.info(f"[Worker Tool Exec] {name} with args: {json.dumps(args)}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
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
                    "url": url,
                    "method": "POST",
                    "payload": payload
                })

                resp = await client.post(url, json=payload)
                
                # Emit result before raising error, to see what happened
                try:
                    resp_json = resp.json()
                except:
                    resp_json = {"text": resp.text}

                await _emit(on_chunk, {
                    "type": "api_call_end",
                    "url": url,
                    "status": resp.status_code,
                    "response": resp_json
                })
                
                resp.raise_for_status()
                return json.dumps(resp.json())

            elif name == "get_legislation_text":
                url = f"{LEX_API_URL}/legislation/text"
                payload = {"legislation_id": args["legislation_id"]}

                await _emit(on_chunk, {
                    "type": "api_call_start",
                    "url": url,
                    "method": "POST",
                    "payload": payload
                })

                resp = await client.post(url, json=payload)

                try:
                    resp_json = resp.json()
                except:
                    resp_json = {"text": resp.text}

                await _emit(on_chunk, {
                    "type": "api_call_end",
                    "url": url,
                    "status": resp.status_code,
                    "response": resp_json
                })

                resp.raise_for_status()
                return json.dumps(resp.json())

            else:
                return f"Error: Tool {name} not found in worker toolset."

    except httpx.HTTPStatusError as e:
        logger.error(f"[Tool Error] {name}: {e.response.text}")
        return f"Error executing tool: {e.response.text}"
    except Exception as e:
        logger.error(f"[Tool Error] {name}: {e}")
        return f"Error executing tool: {str(e)}"
