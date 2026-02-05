import httpx
import logging

try:
    response = httpx.post(
        "http://localhost:8000/api/auth/login",
        json={"username": "admin", "password": "admin"},
        timeout=10
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
