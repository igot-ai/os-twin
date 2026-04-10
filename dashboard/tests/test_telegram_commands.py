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


# ── /startplan with optional plan_id ───────────────────────────────

@pytest.mark.asyncio
async def test_startplan_no_args_shows_menu():
    """'/startplan' with no args shows the plan selection keyboard."""
    plans = [{"id": "plan-1", "label": "Blog (Apr 08)"}]
    with patch("dashboard.telegram_poller.get_config", return_value={"authorized_chats": ["123"]}), \
         patch("dashboard.telegram_poller._get_available_plans", return_value=plans), \
         patch("dashboard.telegram_poller.send_inline_keyboard", new_callable=AsyncMock) as mock_kb:
        await tp._cmd_startplan_menu("fake_token", 123)
        mock_kb.assert_called_once()
        args, _ = mock_kb.call_args
        assert "Select a Plan to Launch" in args[2]
        keyboard = args[3]
        assert any("plan-1" in btn["callback_data"] for row in keyboard for btn in row)


@pytest.mark.asyncio
async def test_startplan_no_args_no_plans():
    """'/startplan' with no plans available shows info message."""
    with patch("dashboard.telegram_poller.get_config", return_value={"authorized_chats": ["123"]}), \
         patch("dashboard.telegram_poller._get_available_plans", return_value=[]), \
         patch("dashboard.telegram_poller.send_reply", new_callable=AsyncMock) as mock_send:
        await tp._cmd_startplan_menu("fake_token", 123)
        mock_send.assert_called_once()
        assert "No plans found" in mock_send.call_args[0][2]


@pytest.mark.asyncio
async def test_startplan_valid_plan_id_goes_to_launch_prompt():
    """'/startplan my-plan' with a valid plan_id skips menu and shows launch confirmation."""
    mock_plan_path = MagicMock()
    mock_plan_path.exists.return_value = True
    with patch("dashboard.telegram_poller.get_config", return_value={"authorized_chats": ["123"]}), \
         patch("dashboard.telegram_poller.find_plan_file", return_value=mock_plan_path), \
         patch("dashboard.telegram_poller.send_inline_keyboard", new_callable=AsyncMock) as mock_kb:

        await tp.handle_message({"chat": {"id": 123}, "text": "/startplan my-plan"}, "fake_token")

        mock_kb.assert_called_once()
        args, _ = mock_kb.call_args
        assert "Confirm Launch" in args[2]
        keyboard = args[3]
        assert any("launch_confirm:my-plan" in btn["callback_data"] for row in keyboard for btn in row)


@pytest.mark.asyncio
async def test_startplan_invalid_plan_id_shows_error_and_list():
    """'/startplan nonexistent' with an invalid plan_id shows error + available plans."""
    plans = [{"id": "blog-site", "label": "Blog Site (Apr 08)"}, {"id": "snake-game", "label": "Snake Game (Apr 07)"}]
    with patch("dashboard.telegram_poller.get_config", return_value={"authorized_chats": ["123"]}), \
         patch("dashboard.telegram_poller.find_plan_file", return_value=None), \
         patch("dashboard.telegram_poller._get_available_plans", return_value=plans), \
         patch("dashboard.telegram_poller.send_reply", new_callable=AsyncMock) as mock_send, \
         patch("dashboard.telegram_poller.send_inline_keyboard", new_callable=AsyncMock) as mock_kb:

        await tp.handle_message({"chat": {"id": 123}, "text": "/startplan nonexistent"}, "fake_token")

        # Should send error message with plan list
        mock_send.assert_called_once()
        error_msg = mock_send.call_args[0][2]
        assert "not found" in error_msg
        assert "`nonexistent`" in error_msg
        assert "`blog-site`" in error_msg
        assert "`snake-game`" in error_msg

        # Should also show the selection keyboard
        mock_kb.assert_called_once()
        args, _ = mock_kb.call_args
        assert "Select a Plan to Launch" in args[2]


@pytest.mark.asyncio
async def test_startplan_invalid_plan_id_no_plans_available():
    """'/startplan nonexistent' when no plans exist shows error without keyboard."""
    with patch("dashboard.telegram_poller.get_config", return_value={"authorized_chats": ["123"]}), \
         patch("dashboard.telegram_poller.find_plan_file", return_value=None), \
         patch("dashboard.telegram_poller._get_available_plans", return_value=[]), \
         patch("dashboard.telegram_poller.send_reply", new_callable=AsyncMock) as mock_send, \
         patch("dashboard.telegram_poller.send_inline_keyboard", new_callable=AsyncMock) as mock_kb:

        await tp.handle_message({"chat": {"id": 123}, "text": "/startplan bad-id"}, "fake_token")

        mock_send.assert_called_once()
        error_msg = mock_send.call_args[0][2]
        assert "not found" in error_msg
        assert "No plans found" in error_msg

        # No keyboard shown when there are no plans
        mock_kb.assert_not_called()


@pytest.mark.asyncio
async def test_startplan_plan_id_with_extra_whitespace():
    """'/startplan   my-plan  ' trims whitespace correctly."""
    mock_plan_path = MagicMock()
    with patch("dashboard.telegram_poller.get_config", return_value={"authorized_chats": ["123"]}), \
         patch("dashboard.telegram_poller.find_plan_file", return_value=mock_plan_path) as mock_find, \
         patch("dashboard.telegram_poller.send_inline_keyboard", new_callable=AsyncMock) as mock_kb:

        await tp.handle_message({"chat": {"id": 123}, "text": "/startplan   my-plan  "}, "fake_token")

        # Should have called find_plan_file("my-plan") (trimmed)
        mock_find.assert_called_with("my-plan")
        mock_kb.assert_called_once()
        args, _ = mock_kb.call_args
        assert "Confirm Launch" in args[2]
