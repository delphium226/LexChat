import asyncio
import json
import httpx

API_URL = "http://localhost:8000/api/system/chat"

async def test_system_chat():
    payload = {
        "model": "mistral-large-3:675b-cloud",  # Use a model known to have tools or strong capability
        "messages": [
            {"role": "user", "content": "Search for the Data Protection Act 2018 and summarize its key principles."}
        ]
    }
    
    # We want to force a tool call if possible. "Search for..." should trigger it.
    # Note: The server needs to be running.
    
    print(f"Connecting to {API_URL}...")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", API_URL, json=payload) as response:
                if response.status_code != 200:
                    print(f"Failed: {response.status_code}")
                    print(await response.read())
                    return

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                            event_type = data.get("type")
                            
                            if event_type == "token":
                                print(f"[TOKEN] {data.get('content')}", end="", flush=True)
                            elif event_type == "tool_call":
                                print(f"\n[TOOL CALL] {json.dumps(data.get('tool_calls'), indent=2)}")
                            elif event_type == "tool_result":
                                print(f"\n[TOOL RESULT] {data.get('tool')} -> {data.get('result')[:100]}...")
                            elif event_type == "result":
                                print(f"\n[RESULT] {data.get('message')}")
                            elif event_type == "error":
                                print(f"\n[ERROR] {data.get('error')}")
                            elif event_type == "queue":
                                print(f"\n[QUEUE] Position: {data.get('position')}")
                            else:
                                print(f"\n[EVENT] {data}")
                                
                        except json.JSONDecodeError:
                            print(f"\n[RAW] {line}")
                            
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    asyncio.run(test_system_chat())
