import asyncio
import json
import httpx
import os

# We need to test against the running server.
# However, deep research is disabled by default now.
# We can't easily change the running server's config without restart.
# BUT, we can try to force it if we had an endpoint to update settings, which we don't.
# 
# WAIT. The user asked for a flag in the settings file.
# The `settings` object is loaded from environment variables or .env file.
# If I change the .env file and restart the server, it will be enabled.
#
# Alternatively, I can mock the test to hit the system endpoint and hope the "search" tool was called?
# No, `delegate_research` is only added if enabled.
# 
# So I must:
# 1. Modify .env to enable deep research.
# 2. Restart backend.
# 3. Run test script.
# 4. Revert .env.
# 5. Restart backend.
#
# This is heavy but necessary for true verification.

API_URL = "http://localhost:8000/api/system/chat"

async def test_api_logging():
    payload = {
        "model": "mistral-large-3:675b-cloud",
        "messages": [
            {"role": "user", "content": "Search for the Data Protection Act 2018."}
        ]
    }
    
    print(f"Connecting to {API_URL}...")
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", API_URL, json=payload) as response:
                if response.status_code != 200:
                    print(f"Failed: {response.status_code}")
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                            event_type = data.get("type")
                            
                            if event_type == "api_call_start":
                                print(f"\n[API START] {data['url']}")
                                print(f"Payload: {json.dumps(data['payload'], indent=2)}")
                            elif event_type == "api_call_end":
                                print(f"\n[API END] Status: {data['status']}")
                                print(f"Response: {str(data['response'])[:100]}...")
                            elif event_type == "tool_call":
                                print(f"\n[TOOL CALL] {data['tool_calls'][0]['function']['name']}")
                                
                        except json.JSONDecodeError:
                            pass
                            
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    asyncio.run(test_api_logging())
