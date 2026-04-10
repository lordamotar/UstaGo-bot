import requests

def test_login():
    url = "http://localhost:8000/api/v1/auth/login"
    data = {
        "username": "admin",
        "password": "admin123"
    }
    
    print(f"Testing login at {url}...")
    try:
        response = requests.post(url, data=data)
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text}")
        
        if response.status_code == 200:
            token = response.json().get("access_token")
            print("Login successful!")
            
            # Test /me
            me_url = "http://localhost:8000/api/v1/auth/me"
            headers = {"Authorization": f"Bearer {token}"}
            me_resp = requests.get(me_url, headers=headers)
            print(f"Me Status: {me_resp.status_code}")
            print(f"Me Body: {me_resp.text}")
        else:
            print("Login failed.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_login()
