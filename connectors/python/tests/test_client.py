import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from connectors.client import ConnectorHttpClient
from tenacity import RetryError

@pytest.mark.asyncio
async def test_client_get():
    client = ConnectorHttpClient(base_url="http://api.test", headers={"X-Test": "val"})
    
    # Mocking the client and its request method
    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_request.return_value = mock_response
        
        resp = await client.get("/test", params={"q": "1"})
        
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        mock_request.assert_called_once()
        
    await client.close()

@pytest.mark.asyncio
async def test_client_retries():
    client = ConnectorHttpClient(base_url="http://api.test")
    
    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
        # 1st attempt: 500 error
        resp500 = MagicMock(spec=httpx.Response)
        resp500.status_code = 500
        # Mocking raise_for_status to actually raise
        resp500.raise_for_status.side_effect = httpx.HTTPStatusError("500", request=MagicMock(), response=resp500)
        
        # 2nd attempt: Success
        resp200 = MagicMock(spec=httpx.Response)
        resp200.status_code = 200
        
        mock_request.side_effect = [resp500, resp200]
        
        # We need to lower the wait time for tests if possible, 
        # but tenacity is decorated on the method.
        # Alternatively, we just mock the retry decorator or trust it works.
        # Let's try to run it with short wait.
        
        with patch("tenacity.nap.time.sleep", return_value=None):
            resp = await client.get("/test")
            assert resp.status_code == 200
            assert mock_request.call_count == 2
            
    await client.close()

@pytest.mark.asyncio
async def test_client_max_retries():
    client = ConnectorHttpClient(base_url="http://api.test")
    
    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
        resp500 = MagicMock(spec=httpx.Response)
        resp500.status_code = 500
        resp500.raise_for_status.side_effect = httpx.HTTPStatusError("500", request=MagicMock(), response=resp500)
        
        mock_request.return_value = resp500
        
        with patch("tenacity.nap.time.sleep", return_value=None):
            with pytest.raises(httpx.HTTPStatusError):
                await client.get("/test")
            
            assert mock_request.call_count == 3
            
    await client.close()

@pytest.mark.asyncio
async def test_client_all_methods():
    client = ConnectorHttpClient(base_url="http://api.test")
    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        await client.post("/test", json={"a": 1})
        await client.put("/test", json={"a": 2})
        await client.delete("/test")
        
        assert mock_request.call_count == 3
        
    await client.close()
    assert client._client is None
