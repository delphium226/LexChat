import httpx
import json
import asyncio

async def test_chat():
    url = "http://localhost:80/api/chat"
    headers = {"Content-Type": "application/json"}
    
    # payload from user request
    payload = {
        "model": "mistral-large-3:675b-cloud", # Assuming this is available
        "messages": [
            {"role": "user", "content": "What powers of direction do the Scottish Ministers have in relation to Health Boards in Scotland?"}
        ],
        "deep_research": True # Enable usage of tools if implemented
    }

    print(f"Sending query to {url}...")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                print(f"Status: {response.status_code}")
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                            if data["type"] == "token":
                                print(data["content"], end="", flush=True)
                            elif data["type"] == "result":
                                print("\n\n[DONE]")
                            elif data["type"] == "error":
                                print(f"\n[ERROR] {data['error']}")
                            elif "tool" in data:
                                print(f"\n[TOOL] {data['type']}: {data['tool']}")
                        except:
                            print(f"\n[RAW] {data_str}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_chat())
