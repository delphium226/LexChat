
import asyncio
import httpx
import json

LEX_API_URL = "https://lex.lab.i.ai.gov.uk"

async def test_search(query):
    url = f"{LEX_API_URL}/legislation/search"
    payload = {
        "query": query,
        "limit": 5,
        "include_text": False
    }
    print(f"Searching: {query}")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            json_str = json.dumps(data)
            print(f"Status: {resp.status_code}")
            print(f"Response Length: {len(json_str)} characters")
            # print(f"Preview: {json_str[:200]}...")
        except Exception as e:
            print(f"Error: {e}")

async def main():
    queries = [
        "Public Bodies (Joint Working) (Scotland) Act 2014",
        "Integration Joint Board strategic plan regulations Scotland",
        "Integration Joint Board strategic plan guidance Scotland"
    ]
    
    for q in queries:
        await test_search(q)
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(main())
