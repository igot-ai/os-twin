import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from dashboard.telegram_sessions import get_session, clear_session, set_plan, set_mode, _sessions
import dashboard.telegram_poller as tp

@pytest.fixture(autouse=True)
def clean_sessions():
    _sessions.clear()
    yield
    _sessions.clear()

def test_session_management():
    # Test get_session
    session = get_session(123)
    assert session.chat_id == 123
    assert session.mode == "idle"
    
    # Test set_mode and set_plan
    set_mode(123, "editing")
    set_plan(123, "plan-1")
    
    session = get_session(123)
    assert session.mode == "editing"
    assert session.active_plan_id == "plan-1"
    
    # Test clear_session
    clear_session(123)
    session = get_session(123)
    assert session.mode == "idle"
    assert session.active_plan_id is None

@pytest.mark.asyncio
async def test_cmd_menu():
    with patch("dashboard.telegram_poller.send_inline_keyboard", new_callable=AsyncMock) as mock_send:
        await tp._cmd_menu("fake_token", 123)
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        assert args[1] == 123
        keyboard = args[3]
        assert any(btn["callback_data"] == "menu:cat:monitoring" for row in keyboard for btn in row)
        assert any(btn["callback_data"] == "menu:cat:plans" for row in keyboard for btn in row)
        assert any(btn["callback_data"] == "menu:cat:system" for row in keyboard for btn in row)

@pytest.mark.asyncio
async def test_submenu_monitoring():
    with patch("dashboard.telegram_poller.send_inline_keyboard", new_callable=AsyncMock) as mock_send:
        await tp._cmd_submenu_monitoring("fake_token", 123)
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        keyboard = args[3]
        assert any(btn["callback_data"] == "cmd:dashboard" for row in keyboard for btn in row)
        assert any(btn["callback_data"] == "menu:main" for row in keyboard for btn in row)

@pytest.mark.asyncio
async def test_submenu_plans():
    with patch("dashboard.telegram_poller.send_inline_keyboard", new_callable=AsyncMock) as mock_send:
        await tp._cmd_submenu_plans("fake_token", 123)
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        keyboard = args[3]
        assert any(btn["callback_data"] == "cmd:draft_prompt" for row in keyboard for btn in row)
        assert any(btn["callback_data"] == "menu:main" for row in keyboard for btn in row)

@pytest.mark.asyncio
async def test_submenu_system():
    with patch("dashboard.telegram_poller.send_inline_keyboard", new_callable=AsyncMock) as mock_send:
        await tp._cmd_submenu_system("fake_token", 123)
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        keyboard = args[3]
        assert any(btn["callback_data"] == "cmd:new" for row in keyboard for btn in row)
        assert any(btn["callback_data"] == "menu:main" for row in keyboard for btn in row)

@pytest.mark.asyncio
async def test_register_commands():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        await tp.register_commands("fake_token")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "setMyCommands" in args[0]
        assert "commands" in kwargs["json"]
        commands = kwargs["json"]["commands"]
        assert any(c["command"] == "menu" for c in commands)
        assert any(c["command"] == "dashboard" for c in commands)

@pytest.mark.asyncio
async def test_handle_callback_query():
    update = {
        "callback_query": {
            "id": "query_1",
            "message": {"chat": {"id": 123}},
            "data": "menu:plans"
        }
    }
    
    with patch("dashboard.telegram_poller.get_config", return_value={"authorized_chats": ["123"]}), \
         patch("dashboard.telegram_poller.answer_callback_query", new_callable=AsyncMock) as mock_answer, \
         patch("dashboard.telegram_poller.send_reply", new_callable=AsyncMock) as mock_send, \
         patch("dashboard.telegram_poller._cmd_plans", return_value="Plan List"):
         
        await tp.handle_callback_query(update, "fake_token")
        
        mock_answer.assert_called_once_with("fake_token", "query_1")
        mock_send.assert_called_once_with("fake_token", 123, "Plan List")

@pytest.mark.asyncio
async def test_callback_launch_prompt():
    update = {
        "callback_query": {
            "id": "query_2",
            "message": {"chat": {"id": 123}},
            "data": "menu:launch_prompt:plan-1"
        }
    }
    with patch("dashboard.telegram_poller.get_config", return_value={"authorized_chats": ["123"]}), \
         patch("dashboard.telegram_poller.answer_callback_query", new_callable=AsyncMock) as mock_answer, \
         patch("dashboard.telegram_poller.send_inline_keyboard", new_callable=AsyncMock) as mock_send:
         
        await tp.handle_callback_query(update, "fake_token")
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        assert args[1] == 123
        assert "Confirm Launch" in args[2]

@pytest.mark.asyncio
async def test_callback_cmd_dispatch():
    update = {
        "callback_query": {
            "id": "query_3",
            "message": {"chat": {"id": 123}},
            "data": "cmd:dashboard"
        }
    }
    with patch("dashboard.telegram_poller.get_config", return_value={"authorized_chats": ["123"]}), \
         patch("dashboard.telegram_poller.answer_callback_query", new_callable=AsyncMock) as mock_answer, \
         patch("dashboard.telegram_poller.send_reply", new_callable=AsyncMock) as mock_send, \
         patch("dashboard.telegram_poller._cmd_dashboard", return_value="Dashboard Art"):
         
        await tp.handle_callback_query(update, "fake_token")
        mock_send.assert_called_once_with("fake_token", 123, "Dashboard Art")
    # Test when AI is unavailable
    with patch("dashboard.telegram_poller.send_reply", new_callable=AsyncMock) as mock_send, \
         patch("dashboard.telegram_poller.AI_AVAILABLE", False):
        await tp._cmd_draft("fake_token", 123, "/draft Build something")
        mock_send.assert_called_with("fake_token", 123, "⚠️ AI features are not available because `deepagents` or API keys are not configured.")

@pytest.mark.asyncio
async def test_cancel_command():
    set_mode(123, "editing")
    with patch("dashboard.telegram_poller.send_reply", new_callable=AsyncMock) as mock_send, \
         patch("dashboard.telegram_poller.get_config", return_value={"authorized_chats": ["123"]}):
        await tp.handle_message({"chat": {"id": 123}, "text": "/cancel"}, "fake_token")
        
        session = get_session(123)
        assert session.mode == "idle"
        assert session.active_plan_id is None

@pytest.mark.asyncio
async def test_stateful_routing():
    # Setup editing mode
    set_mode(123, "editing")
    set_plan(123, "plan-1")
    
    with patch("dashboard.telegram_poller.send_reply", new_callable=AsyncMock) as mock_send, \
         patch("dashboard.telegram_poller.AI_AVAILABLE", True), \
         patch("dashboard.telegram_poller.refine_plan", new_callable=AsyncMock, create=True) as mock_refine:
         
        mock_refine.return_value = "Refined plan content"
        
        # Test routing plain text
        await tp._handle_stateful_text("fake_token", 123, "Make it better", get_session(123))
        
        mock_refine.assert_called_once()
        args, kwargs = mock_refine.call_args
        assert kwargs["user_message"] == "Make it better"
        assert len(kwargs["chat_history"]) == 0
