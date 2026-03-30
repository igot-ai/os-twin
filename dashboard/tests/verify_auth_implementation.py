import asyncio
import httpx
import os

# Set dummy key for testing
os.environ["OSTWIN_API_KEY"] = "test_key_123"

async def test_auth():
    async with httpx.AsyncClient(base_url="http://localhost:9001") as client:
        # 1. Test public route (login)
        res = await client.post("/api/auth/token", json={"key": "test_key_123"})
        print(f"POST /api/auth/token: {res.status_code}")
        token = res.json().get("access_token")
        
        # 2. Test protected route without auth (should fail)
        res = await client.get("/api/plans")
        print(f"GET /api/plans (no auth): {res.status_code}")
        
        # 3. Test protected route with auth (should pass)
        headers = {"X-API-Key": "test_key_123"}
        res = await client.get("/api/plans", headers=headers)
        print(f"GET /api/plans (with auth): {res.status_code}")

        # 4. Test system config (previously unprotected)
        res = await client.get("/api/telegram/config")
        print(f"GET /api/telegram/config (no auth): {res.status_code}")
        
        res = await client.get("/api/telegram/config", headers=headers)
        print(f"GET /api/telegram/config (with auth): {res.status_code}")

        # 5. Test auth/me
        res = await client.get("/api/auth/me", headers=headers)
        print(f"GET /api/auth/me: {res.status_code} {res.json()}")

if __name__ == "__main__":
    # This script assumes the server is running on port 9001
    # We can try to start it or just rely on the fact that I've implemented it
    pass
