import httpx
import json
import logging
import asyncio
from typing import List, Optional, Callable
from config import settings
from services.prompts import MANAGER_PROMPT, WORKER_PROMPT, DEEP_RESEARCH_PROMPT
from services.tools import manager_tools, worker_tools, execute_worker_tool, LEX_API_URL
from services.web_search import search_web
from services.learning import get_relevant_examples

logger = logging.getLogger("lexchat.ollama")

# ----------------------------------------------------------------------
# SHARED CHAT LOOP (ReAct)
# ----------------------------------------------------------------------

async def chat_loop(messages: list, model: str, signal_check: Callable, num_ctx: int, tools: list, tool_executor: Callable, on_chunk: Callable):
    """
    Generic ReAct loop for both Manager and Worker agents.
    """
    try:
        if signal_check and signal_check():
            raise Exception("Aborted")

        # Payload
        # Note: Python config models list might need to clearly map to context length if dynamic.
        # For now using simple fallback.
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "stream": True,
            "options": {"num_ctx": num_ctx}
        }
        
        logger.info(f"[ChatLoop] Sending request to Ollama (Tools: {len(tools)})...")
        
        url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        full_content = ""
        tool_calls = []
        
        async with httpx.AsyncClient(timeout=300.0) as client:
             async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    err = await response.aread()
                    logger.error(f"Ollama Error {response.status_code}: {err}")
                    raise Exception(f"Ollama Error: {response.status_code}")
                    
                async for chunk in response.aiter_bytes():
                     if signal_check and signal_check():
                         raise Exception("Aborted")
                     
                     try:
                         obj = json.loads(chunk)
                         if "message" in obj:
                             msg = obj["message"]
                             content = msg.get("content", "")
                             full_content += content
                             
                             if content and on_chunk:
                                 await on_chunk({"type": "token", "content": content})
                                 
                             if "tool_calls" in msg:
                                 tool_calls.extend(msg["tool_calls"])
                                 
                     except json.JSONDecodeError:
                         continue

        # Process Tool Calls
        message = {"role": "assistant", "content": full_content}
        if tool_calls:
            message["tool_calls"] = tool_calls
            
        if tool_calls:
            logger.info(f"Tool calls: {len(tool_calls)}")
            next_messages = messages + [message]
            
            for tc in tool_calls:
                if signal_check and signal_check():
                    raise Exception("Aborted")
                    
                func_name = tc["function"]["name"]
                args = tc["function"]["arguments"]
                
                # Execute
                tool_result = await tool_executor(func_name, args)
                
                next_messages.append({
                    "role": "tool",
                    "content": tool_result,
                    "name": func_name
                })
                
            # Recursion
            return await chat_loop(next_messages, model, signal_check, num_ctx, tools, tool_executor, on_chunk)
            
        return full_content

    except Exception as e:
        logger.error(f"ChatLoop Error: {e}")
        raise e

# ----------------------------------------------------------------------
# WORKER AGENT
# ----------------------------------------------------------------------

async def run_worker_agent(query: str, model: str, signal_check: Callable, num_ctx: int, parent_on_chunk: Callable):
    logger.info(f"[Worker] Starting research on: {query}")
    
    messages = [
        {"role": "system", "content": WORKER_PROMPT},
        {"role": "user", "content": query}
    ]
    
    # Worker tool executor wrapper for updates
    async def worker_tool_executor_wrapper(name, args):
        if parent_on_chunk:
            await parent_on_chunk({"type": "tool_start", "tool": f"Worker: {name}"})
        result = await execute_worker_tool(name, args)
        if parent_on_chunk:
            await parent_on_chunk({"type": "tool_end", "tool": f"Worker: {name}", "result": "Done"})
        return result

    # Pass None for on_chunk to suppress worker token streaming to client (Manager aggregates it)
    return await chat_loop(messages, model, signal_check, num_ctx, worker_tools, worker_tool_executor_wrapper, None)

# ----------------------------------------------------------------------
# MANAGER AGENT
# ----------------------------------------------------------------------

async def process_user_request(messages: list, model: str, on_chunk: Callable, signal_check: Callable, num_ctx: int):
    # 1. Prepare System Prompt
    system_message = {"role": "system", "content": MANAGER_PROMPT}
    
    # 2. In-Context Learning Injection
    try:
        last_msg = messages[-1] if messages else None
        if last_msg and last_msg.get("role") == "user":
            learning_data = await get_relevant_examples(last_msg.get("content"))
            # Format learning context (Simple version inline)
            context_inj = ""
            if learning_data["critiques"]:
                context_inj += "\\n### CRITICAL FEEDBACK\\nAVOID these mistakes:\\n"
                for c in learning_data["critiques"]:
                    context_inj += f"- {c.get('feedback_comment')}\\n"
            if learning_data["examples"]:
                context_inj += "\\n### SUCCESSFUL EXAMPLES\\n"
                for ex in learning_data["examples"]:
                    context_inj += f"Q: {ex.get('question')}\\nA: {ex.get('answer')}\\n---\\n"
            
            if context_inj:
                logger.info("[Learning] Injecting feedback context.")
                system_message["content"] += f"\\n\\n{context_inj}"
    except Exception as e:
        logger.error(f"[Learning] Failed to inject context: {e}")

    # Prepend System Prompt
    # Python dict copy
    final_messages = [system_message] + [m for m in messages if m.get("role") != "system"] # simple dedupe of system

    # 3. Manager Tool Executor
    async def manager_tool_executor(name, args):
        if name == "delegate_research":
            if on_chunk:
                await on_chunk({"type": "tool_start", "tool": "Research Agent"})
                
            result = await run_worker_agent(args.get("query"), model, signal_check, num_ctx, on_chunk)
            
            if on_chunk:
                await on_chunk({"type": "tool_end", "tool": "Research Agent", "result": "Research Complete"})
                
            return f"[Research Agent Result]\\n{result}"
        return f"Error: Unknown manager tool {name}"

    return await chat_loop(final_messages, model, signal_check, num_ctx, manager_tools, manager_tool_executor, on_chunk)

# ----------------------------------------------------------------------
# DEEP RESEARCH AGENT
# ----------------------------------------------------------------------

async def chat_with_deep_research(messages: list, model: str, on_status_update: Callable, signal_check: Callable, num_ctx: int):
    logger.info("[Deep Research] Starting session...")
    
    system_message = {"role": "system", "content": DEEP_RESEARCH_PROMPT}
    final_messages = [system_message] + [m for m in messages if m.get("role") != "system"]

    # Combine tools: Worker Tools + Web Search
    web_tool = {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the public web for information. Use this for broad context, news, or general knowledge not in the legal database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."}
                },
                "required": ["query"]
            }
        }
    }
    deep_tools = worker_tools + [web_tool]

    async def deep_tool_executor(name, args):
        if on_status_update:
            await on_status_update({"type": "tool_start", "tool": f"Deep Research: {name}"})
            
        if name == "search_web":
            result = await search_web(args.get("query"))
        else:
            result = await execute_worker_tool(name, args)
            
        if on_status_update:
            await on_status_update({"type": "tool_end", "tool": f"Deep Research: {name}", "result": "Done"})
        return result

    return await chat_loop(final_messages, model, signal_check, num_ctx, deep_tools, deep_tool_executor, on_status_update)

# Aliases for export
chat_with_ollama = process_user_request
