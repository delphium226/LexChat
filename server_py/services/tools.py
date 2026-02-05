import httpx
import json
import logging
from config import settings

logger = logging.getLogger("lexchat.tools")

LEX_API_URL = settings.LEX_API_URL

# Manager Tools
manager_tools = [
    {
        "type": "function",
        "function": {
            "name": "delegate_research",
            "description": "Delegates a complex legal research task to a specialized agent. Use this for any question about UK legislation, case law, or legal concepts.",
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
    }
]

# Worker Tools
worker_tools = [
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
                        "description": "The search query (e.g., 'Computer Misuse Act', 'speeding fines').",
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
                        "description": "The legislation ID (e.g., 'ukpga/1990/18').",
                    },
                },
                "required": ["legislation_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_caselaw",
            "description": "Search for UK court cases and judgments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (e.g., 'Donoghue v Stevenson', 'negligence duty of care').",
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
]

async def execute_worker_tool(name: str, args: dict) -> str:
    logger.info(f"[Worker Tool Exec] {name} with args: {args}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            if name == 'search_legislation':
                response = await client.post(f"{LEX_API_URL}/legislation/search", json={
                    "query": args.get("query"),
                    "year_from": args.get("year_from"),
                    "year_to": args.get("year_to"),
                    "limit": 5,
                    "include_text": False
                })
                return json.dumps(response.json())

            elif name == 'get_legislation_text':
                response = await client.post(f"{LEX_API_URL}/legislation/text", json={
                    "legislation_id": args.get("legislation_id"),
                })
                return json.dumps(response.json())

            elif name == 'search_caselaw':
                response = await client.post(f"{LEX_API_URL}/caselaw/search", json={
                    "query": args.get("query"),
                    "year_from": args.get("year_from"),
                    "year_to": args.get("year_to"),
                    "size": 5
                })
                return json.dumps(response.json())

            else:
                return f"Error: Tool {name} not found in worker toolset."

        except httpx.HTTPStatusError as e:
             logger.error(f"[Tool Error] {name}: {e.response.text}")
             return f"Error executing tool: {e.response.text}"
        except Exception as e:
            logger.error(f"[Tool Error] {name}: {e}")
            return f"Error executing tool: {str(e)}"
