import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from dashboard.chat_adapters import TelegramAdapter, DiscordAdapter, SlackAdapter, registry

@pytest.mark.asyncio
async def test_telegram_adapter_send_message():
    config = {"bot_token": "test_token", "chat_id": "test_chat"}
    adapter = TelegramAdapter(config)
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = await adapter.send_message("Hello Telegram")
        
        assert result is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "test_token" in args[0]
        assert kwargs["json"]["text"] == "Hello Telegram"

@pytest.mark.asyncio
async def test_discord_adapter_send_message():
    config = {"webhook_url": "https://discord.com/api/webhooks/test"}
    adapter = DiscordAdapter(config)
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=204)
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = await adapter.send_message("Hello Discord")
        
        assert result is True
        mock_post.assert_called_once_with(config["webhook_url"] + "?wait=true", json={"content": "Hello Discord"})

@pytest.mark.asyncio
async def test_slack_adapter_send_message():
    config = {"webhook_url": "https://hooks.slack.com/services/test"}
    adapter = SlackAdapter(config)
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = await adapter.send_message("Hello Slack")
        
        assert result is True
        mock_post.assert_called_once_with(config["webhook_url"], json={"text": "Hello Slack"})

def test_registry_get_adapter():
    registry.configs["telegram"] = {"bot_token": "t", "chat_id": "c"}
    adapter = registry.get_adapter("telegram")
    assert isinstance(adapter, TelegramAdapter)
    assert adapter.config["bot_token"] == "t"

    adapter = registry.get_adapter("unknown")
    assert adapter is None

@pytest.mark.asyncio
async def test_api_routes():
    from fastapi.testclient import TestClient
    from dashboard.api import app
    
    # Mock authentication by overriding the dependency in the app
    from dashboard.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"username": "testuser"}
    
    try:
        client = TestClient(app)
        
        # Test GET config
        response = client.get("/api/chat-adapters/config")
        assert response.status_code == 200
        assert isinstance(response.json(), dict)
        
        # Test POST config
        config_data = {
            "platform": "discord",
            "config": {"webhook_url": "https://discord.com/test"}
        }
        response = client.post("/api/chat-adapters/config", json=config_data)
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        # Verify config was updated in registry
        assert registry.configs["discord"]["webhook_url"] == "https://discord.com/test"
        
        # Test POST test endpoint (mocking the send_message)
        with patch("dashboard.chat_adapters.discord.DiscordAdapter.send_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            response = client.post("/api/chat-adapters/discord/test")
            assert response.status_code == 200
            assert response.json()["status"] == "success"
            mock_send.assert_called_once()
    finally:
        # Clean up dependency overrides
        app.dependency_overrides.clear()
