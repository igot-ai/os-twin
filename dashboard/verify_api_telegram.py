import asyncio
import httpx
import sys
import os

async def test_api_telegram():
    base_url = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:" + os.environ.get("OSTWIN_DASHBOARD_PORT", "9000"))
    async with httpx.AsyncClient(base_url=base_url) as client:
        try:
            # 1. Get initial config
            resp = await client.get("/api/telegram/config")
            print(f"GET /api/telegram/config: {resp.status_code}")
            print(f"Content: {resp.json()}")

            # 2. Update config
            new_config = {"bot_token": "test_token_123", "chat_id": "test_chat_456"}
            resp = await client.post("/api/telegram/config", json=new_config)
            print(f"POST /api/telegram/config: {resp.status_code}")
            
            # 3. Verify update
            resp = await client.get("/api/telegram/config")
            print(f"GET /api/telegram/config (verified): {resp.json()}")
            
            # 4. Test connection (should fail with invalid token but check if endpoint works)
            resp = await client.post("/api/telegram/test")
            print(f"POST /api/telegram/test: {resp.status_code}")
            print(f"Content: {resp.json()}")

        except Exception:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_api_telegram())
