import httpx as requests

def test_login(username, password):
    url = "http://localhost:80/api/auth/login"
    payload = {
        "username": username,
        "password": password,
        "rememberMe": False
    }
    try:
        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")


print("Testing Admin Login (Correct):")
test_login("admin", "admin")


print("\nTesting User Login:")
test_login("testuser", "testpassword")

print("\nTesting Case Sensitivity (Admin):")
test_login("Admin", "adminpass")
