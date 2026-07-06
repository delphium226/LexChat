
import httpx
import asyncio
import json

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "mistral-large-3:675b-cloud" # Use a known available model

async def test_missing_tool_calls():
    # Construct a history where assistant calls a tool, but we forget to include tool_calls in the history
    messages = [
        {"role": "user", "content": "What is the capital of France?"},
        {"role": "assistant", "content": "", "tool_calls": [
            {
                "function": {
                    "name": "get_capital",
                    "arguments": {}
                }
            }
        ]}, # Now including tool_calls!
        {"role": "tool", "content": "Paris", "name": "get_capital"}
    ]
    
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False
    }
    
    print("Testing chat with orphaned tool message...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(OLLAMA_URL, json=payload, timeout=30.0)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_missing_tool_calls())
