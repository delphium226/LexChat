import requests

# 1. Login to get token
r = requests.post("http://localhost:8000/api/auth/login", data={"username": "admin", "password": "password"}) # default might be admin/admin
if r.status_code != 200:
    r = requests.post("http://localhost:8000/api/auth/login", data={"username": "admin", "password": "admin"})

token = r.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

# 2. Try to rate message 1 
r = requests.put("http://localhost:8000/api/chats/messages/1/rating", json={"rating": 5}, headers=headers)
print("PUT /api/chats/messages/1/rating:", r.status_code)
print(r.text)

# Also test GET /api/users to confirm our fix worked
r = requests.get("http://localhost:8000/api/users", headers=headers)
print("GET /api/users:", r.status_code)
# print(r.text[:200])
