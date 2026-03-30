import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from dashboard.notification_dispatcher import NotificationDispatcher
from dashboard.global_state import Broadcaster

@pytest.mark.asyncio
async def test_notification_dispatcher_filtering():
    dispatcher = NotificationDispatcher()

    # Events in NOTIFY_EVENTS should pass
    assert dispatcher._should_notify("room_created", {"room": {}}) is True
    assert dispatcher._should_notify("room_updated", {"room": {}}) is True
    assert dispatcher._should_notify("room_removed", {"room_id": "123"}) is True
    assert dispatcher._should_notify("room_message", {"room_id": "123"}) is True
    assert dispatcher._should_notify("plans_updated", {}) is True
    assert dispatcher._should_notify("reaction_toggled", {}) is True
    assert dispatcher._should_notify("comment_published", {}) is True

    # Generic levels
    assert dispatcher._should_notify("log", {"level": "error"}) is True
    assert dispatcher._should_notify("log", {"level": "critical"}) is True
    assert dispatcher._should_notify("log", {"level": "escalation"}) is True

    # Unimportant events should be filtered
    assert dispatcher._should_notify("heartbeat", {}) is False
    assert dispatcher._should_notify("log", {"level": "info"}) is False

@pytest.mark.asyncio
async def test_notification_formatting_via_adapter():
    from dashboard.chat_adapters.telegram import TelegramAdapter
    from dashboard.chat_adapters.discord import DiscordAdapter
    from dashboard.chat_adapters.slack import SlackAdapter

    data = {
        "room": {
            "room_id": "room-101",
            "task_ref": "TASK-42",
            "status": "active",
            "goal_done": 3,
            "goal_total": 10,
        }
    }

    tg = TelegramAdapter({"bot_token": "t", "chat_id": "c"})
    text = tg.format_notification("room_created", data)
    assert "New Room Created" in text
    assert "room\\-101" in text or "room-101" in text
    assert "*" in text  # Telegram bold

    dc = DiscordAdapter({"webhook_url": "http://example.com"})
    text = dc.format_notification("room_created", data)
    assert "New Room Created" in text
    assert "room-101" in text
    assert "**" in text  # Discord bold

    sl = SlackAdapter({"webhook_url": "http://example.com"})
    text = sl.format_notification("room_created", data)
    assert "New Room Created" in text
    assert "room-101" in text

@pytest.mark.asyncio
async def test_notification_dispatcher_dispatch():
    dispatcher = NotificationDispatcher()

    with patch("dashboard.notification_dispatcher.registry.get_settings") as mock_get_settings, \
         patch.object(dispatcher, "_send_to_platform", new_callable=AsyncMock) as mock_send:

        mock_get_settings.return_value = {
            "enabled_platforms": ["telegram", "discord"],
        }

        await dispatcher.dispatch("room_created", {"room": {"room_id": "123"}})

        assert mock_send.call_count == 2
        calls = [call.args[0] for call in mock_send.call_args_list]
        assert "telegram" in calls
        assert "discord" in calls

@pytest.mark.asyncio
async def test_broadcaster_integration():
    from dashboard.ws_router import manager

    broadcaster = Broadcaster()

    # Mock manager.broadcast to avoid network issues
    with patch.object(manager, "broadcast", new_callable=AsyncMock) as mock_ws_broadcast, \
         patch("dashboard.global_state.notification_dispatcher.dispatch", new_callable=AsyncMock) as mock_dispatch:

        await broadcaster.broadcast("room_created", {"room": {"room_id": "test-room"}})

        # Verify WS broadcast happened
        mock_ws_broadcast.assert_called_once()

        # Wait a tiny bit for the background task to start
        await asyncio.sleep(0.01)

        # Verify dispatcher was called
        mock_dispatch.assert_called_once_with("room_created", {"room": {"room_id": "test-room"}})

@pytest.mark.asyncio
async def test_dispatcher_non_blocking_failure():
    dispatcher = NotificationDispatcher()

    with patch("dashboard.notification_dispatcher.registry.get_settings") as mock_get_settings, \
         patch("dashboard.notification_dispatcher.registry.get_adapter") as mock_get:

        mock_get_settings.return_value = {
            "enabled_platforms": ["telegram", "discord"],
        }

        mock_telegram = MagicMock()
        mock_telegram.validate_config.return_value = True
        mock_telegram.format_notification.return_value = "test notification"
        mock_telegram.send_message = AsyncMock(side_effect=Exception("Telegram Down"))

        mock_discord = MagicMock()
        mock_discord.validate_config.return_value = True
        mock_discord.format_notification.return_value = "test notification"
        mock_discord.send_message = AsyncMock(return_value=True)

        def side_effect(platform):
            if platform == "telegram": return mock_telegram
            if platform == "discord": return mock_discord
            return None

        mock_get.side_effect = side_effect

        # Should not raise exception because gather uses return_exceptions=True
        await dispatcher.dispatch("room_created", {"room": {"room_id": "test"}})

        mock_telegram.send_message.assert_called_once()
        mock_discord.send_message.assert_called_once()
