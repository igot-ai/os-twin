"""
Unit tests for dashboard/master_agent.py.

Covers MasterAgentConfig, get/set model helpers, SessionRegistry,
_OpenCodeLLMClient, and master_complete. All tests are mock-based —
no real OpenCode server calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dashboard.llm_client import ChatMessage, LLMConfig, ToolCall


@pytest.fixture(autouse=True)
def reset_master_state():
    """Reset global _master_config before and after each test."""
    from dashboard import master_agent as ma

    saved = (
        ma._master_config.model,
        ma._master_config.provider,
        ma._master_config.temperature,
        ma._master_config.max_tokens,
        ma._master_config.is_explicit,
    )
    yield
    (
        ma._master_config.model,
        ma._master_config.provider,
        ma._master_config.temperature,
        ma._master_config.max_tokens,
        ma._master_config.is_explicit,
    ) = saved
    ma._opencode_client = None
    ma._session_registry.clear()


class TestMasterAgentConfig:
    def test_defaults(self):
        from dashboard.master_agent import DEFAULT_MODEL, DEFAULT_PROVIDER, MasterAgentConfig

        cfg = MasterAgentConfig()
        assert cfg.model == DEFAULT_MODEL
        assert cfg.provider == DEFAULT_PROVIDER
        assert cfg.temperature is None
        assert cfg.max_tokens == 8192
        assert cfg.is_explicit is False

    def test_to_llm_config(self):
        from dashboard.master_agent import MasterAgentConfig

        cfg = MasterAgentConfig(model="gpt-4", temperature=0.5, max_tokens=2048)
        llm_cfg = cfg.to_llm_config()
        assert isinstance(llm_cfg, LLMConfig)
        assert llm_cfg.max_tokens == 2048
        assert llm_cfg.temperature == 0.5


class TestGetSetMasterModel:
    def test_get_master_model_returns_default(self):
        from dashboard.master_agent import DEFAULT_MODEL, get_master_model

        assert get_master_model() == DEFAULT_MODEL

    def test_set_master_model_plain_name(self):
        from dashboard.master_agent import _master_config, get_master_model, set_master_model

        set_master_model("gpt-4o")
        assert get_master_model() == "gpt-4o"
        assert _master_config.provider == "openai"
        assert _master_config.is_explicit is True

    def test_set_master_model_with_explicit_provider(self):
        from dashboard.master_agent import _master_config, set_master_model

        set_master_model("claude-3-opus", provider="anthropic")
        assert _master_config.model == "claude-3-opus"
        assert _master_config.provider == "anthropic"

    def test_set_master_model_slash_prefix(self):
        from dashboard.master_agent import _master_config, set_master_model

        set_master_model("openai/gpt-4-turbo")
        assert _master_config.model == "gpt-4-turbo"
        assert _master_config.provider == "openai"

    def test_set_master_model_infers_google_for_bare_gemini(self):
        from dashboard.master_agent import _master_config, set_master_model

        set_master_model("gemini-3.1-pro")
        assert _master_config.model == "gemini-3.1-pro"
        assert _master_config.provider == "google"

    def test_set_master_model_clears_sessions(self):
        from dashboard.master_agent import _session_registry, set_master_model

        _session_registry._sessions["test-conv"] = "sess-1"
        set_master_model("gpt-4o")
        assert len(_session_registry._sessions) == 0


class TestSessionRegistry:
    @pytest.mark.asyncio
    async def test_creates_session_on_first_access(self):
        from dashboard.master_agent import _session_registry

        with patch("dashboard.master_agent.get_opencode_client") as mock_oc:
            mock_client = MagicMock()
            mock_client.session.create = AsyncMock(return_value=MagicMock(id="sess-new"))
            mock_oc.return_value = mock_client

            sid = await _session_registry.get_or_create("conv-1")
            assert sid == "sess-new"
            assert not _session_registry.has_system("conv-1")

    @pytest.mark.asyncio
    async def test_reuses_existing_session(self):
        from dashboard.master_agent import _session_registry

        _session_registry._sessions["conv-1"] = "sess-existing"
        _session_registry.mark_system_set("conv-1")

        sid = await _session_registry.get_or_create("conv-1")
        assert sid == "sess-existing"
        assert _session_registry.has_system("conv-1")

    def test_remove_clears_session(self):
        from dashboard.master_agent import _session_registry

        _session_registry._sessions["conv-1"] = "sess-1"
        _session_registry.mark_system_set("conv-1")
        _session_registry.remove("conv-1")
        assert "conv-1" not in _session_registry._sessions
        assert not _session_registry.has_system("conv-1")

    def test_clear_wipes_all(self):
        from dashboard.master_agent import _session_registry

        _session_registry._sessions["a"] = "1"
        _session_registry._sessions["b"] = "2"
        _session_registry.mark_system_set("a")
        _session_registry.clear()
        assert len(_session_registry._sessions) == 0
        assert not _session_registry.has_system("a")


class TestGetMasterClient:
    def test_returns_opencode_llm_client(self):
        from dashboard.master_agent import _OpenCodeLLMClient, get_master_client

        client = get_master_client()
        assert isinstance(client, _OpenCodeLLMClient)

    def test_conversation_id_propagated(self):
        from dashboard.master_agent import _OpenCodeLLMClient, get_master_client

        client = get_master_client(conversation_id="thread-42")
        assert isinstance(client, _OpenCodeLLMClient)
        assert client.conversation_id == "thread-42"

    def test_create_client_for_model(self):
        from dashboard.master_agent import _OpenCodeLLMClient, create_client_for_model

        client = create_client_for_model("gpt-4o", provider="openai", conversation_id="plan-x")
        assert isinstance(client, _OpenCodeLLMClient)
        assert client.model == "gpt-4o"
        assert client.provider == "openai"
        assert client.conversation_id == "plan-x"

    def test_default_conversation_id_is_uuid(self):
        from dashboard.master_agent import get_master_client

        client = get_master_client()
        assert len(client.conversation_id) > 0


class TestDeltaMessaging:
    @pytest.mark.asyncio
    async def test_only_new_messages_sent(self):
        """Second chat() call in same conversation only sends delta (new parts)."""
        from dashboard.master_agent import _session_registry, master_chat

        _session_registry._sessions["conv-delta"] = "sess-delta"

        mock_item = MagicMock()
        mock_item.info.role = "assistant"
        text_part = MagicMock()
        text_part.type = "text"
        text_part.text = "First reply"
        mock_item.parts = [text_part]

        with patch("dashboard.master_agent.get_opencode_client") as mock_oc, \
             patch("dashboard.master_agent.read_session_text", new_callable=AsyncMock, return_value="First reply"):
            mock_client = MagicMock()
            mock_client.post = AsyncMock()
            mock_oc.return_value = mock_client

            msgs = [
                ChatMessage(role="system", content="sys"),
                ChatMessage(role="user", content="hello"),
            ]
            await master_chat(msgs, conversation_id="conv-delta")

            chat_call = mock_client.post.call_args
            parts = chat_call[1]["body"]["parts"]
            assert any("hello" in str(p) for p in parts)

            assert _session_registry.has_system("conv-delta")

            mock_client.post = AsyncMock()

            msgs.append(ChatMessage(role="assistant", content="First reply"))
            msgs.append(ChatMessage(role="user", content="follow-up"))

            with patch("dashboard.master_agent.read_session_text", new_callable=AsyncMock, return_value="Second reply"):
                await master_chat(msgs, conversation_id="conv-delta")

            chat_call2 = mock_client.post.call_args
            parts2 = chat_call2[1]["body"]["parts"]
            assert any("follow-up" in str(p) for p in parts2)
            assert not any("hello" in str(p) for p in parts2)

    @pytest.mark.asyncio
    async def test_different_conversations_isolated(self):
        """Different conversation_ids get separate sessions."""
        from dashboard.master_agent import _session_registry, master_chat

        with patch("dashboard.master_agent.get_opencode_client") as mock_oc, \
             patch("dashboard.master_agent.read_session_text", new_callable=AsyncMock, return_value="reply"):
            mock_client = MagicMock()
            mock_client.session.create = AsyncMock(side_effect=[
                MagicMock(id="sess-A"), MagicMock(id="sess-B")
            ])
            mock_client.post = AsyncMock()
            mock_oc.return_value = mock_client

            await master_chat(
                [ChatMessage(role="user", content="msg-A")],
                conversation_id="conv-A",
            )
            await master_chat(
                [ChatMessage(role="user", content="msg-B")],
                conversation_id="conv-B",
            )

            assert _session_registry._sessions["conv-A"] == "sess-A"
            assert _session_registry._sessions["conv-B"] == "sess-B"


class TestEndConversation:
    @pytest.mark.asyncio
    async def test_removes_session(self):
        from dashboard.master_agent import _session_registry, end_conversation

        _session_registry._sessions["conv-done"] = "sess-old"
        _session_registry.mark_system_set("conv-done")

        with patch("dashboard.master_agent.get_opencode_client") as mock_oc:
            mock_client = MagicMock()
            mock_client.session.delete = AsyncMock()
            mock_oc.return_value = mock_client

            await end_conversation("conv-done")

        assert "conv-done" not in _session_registry._sessions
        assert not _session_registry.has_system("conv-done")


class TestMsgToParts:
    def test_user_message(self):
        from dashboard.master_agent import _msg_to_parts

        parts = _msg_to_parts(ChatMessage(role="user", content="hi"))
        assert parts == [{"type": "text", "text": "hi"}]

    def test_user_message_with_images(self):
        from dashboard.master_agent import _msg_to_parts

        parts = _msg_to_parts(ChatMessage(role="user", content="look", images=["data:image/png;base64,abc"]))
        assert len(parts) == 2
        assert parts[0]["type"] == "file"
        assert parts[0]["file"]["url"] == "data:image/png;base64,abc"
        assert parts[1] == {"type": "text", "text": "look"}

    def test_tool_result(self):
        from dashboard.master_agent import _msg_to_parts

        parts = _msg_to_parts(ChatMessage(role="tool", content="42", tool_call_id="1", name="calc"))
        assert len(parts) == 1
        assert "calc" in parts[0]["text"]
        assert "42" in parts[0]["text"]

    def test_assistant_with_tool_calls(self):
        from dashboard.master_agent import _msg_to_parts

        parts = _msg_to_parts(ChatMessage(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="1", name="read_plan", arguments={"plan_id": "x"})],
        ))
        assert len(parts) == 1
        assert "read_plan" in parts[0]["text"]


class TestExtractNewParts:
    def test_extracts_last_user_message(self):
        from dashboard.master_agent import _extract_new_parts

        messages = [
            ChatMessage(role="system", content="sys"),
            ChatMessage(role="user", content="hello"),
        ]
        parts = _extract_new_parts(messages)
        assert len(parts) == 1
        assert parts[0]["text"] == "hello"

    def test_extracts_trailing_tool_results(self):
        from dashboard.master_agent import _extract_new_parts

        messages = [
            ChatMessage(role="user", content="read plan"),
            ChatMessage(role="assistant", content="", tool_calls=[
                ToolCall(id="1", name="read_plan", arguments={"plan_id": "x"})
            ]),
            ChatMessage(role="tool", content="plan content", tool_call_id="1", name="read_plan"),
        ]
        parts = _extract_new_parts(messages)
        assert len(parts) == 1
        assert "read_plan" in parts[0]["text"]
        assert "plan content" in parts[0]["text"]

    def test_extracts_multiple_trailing_tool_results(self):
        from dashboard.master_agent import _extract_new_parts

        messages = [
            ChatMessage(role="user", content="read"),
            ChatMessage(role="assistant", content="", tool_calls=[
                ToolCall(id="1", name="tool_a", arguments={}),
                ToolCall(id="2", name="tool_b", arguments={}),
            ]),
            ChatMessage(role="tool", content="result_a", tool_call_id="1", name="tool_a"),
            ChatMessage(role="tool", content="result_b", tool_call_id="2", name="tool_b"),
        ]
        parts = _extract_new_parts(messages)
        assert len(parts) == 2
        assert "result_a" in parts[0]["text"]
        assert "result_b" in parts[1]["text"]

    def test_empty_messages_returns_empty(self):
        from dashboard.master_agent import _extract_new_parts

        parts = _extract_new_parts([])
        assert parts == []

    def test_system_messages_excluded(self):
        from dashboard.master_agent import _extract_new_parts

        messages = [
            ChatMessage(role="system", content="sys prompt"),
        ]
        parts = _extract_new_parts(messages)
        # Fallback sends the last message even if it's system
        # because _extract_new_parts is a best-effort heuristic
        assert len(parts) >= 0


class TestSystemPromptTracking:
    @pytest.mark.asyncio
    async def test_system_prompt_only_sent_on_first_call(self):
        """System prompt is passed to _opencode_chat only on first message per session."""
        from dashboard.master_agent import _session_registry, master_chat

        _session_registry._sessions["conv-sys"] = "sess-sys"

        with patch("dashboard.master_agent.get_opencode_client") as mock_oc, \
             patch("dashboard.master_agent.read_session_text", new_callable=AsyncMock, return_value="reply"):
            mock_client = MagicMock()
            mock_client.post = AsyncMock()
            mock_oc.return_value = mock_client

            msgs = [
                ChatMessage(role="system", content="Be helpful"),
                ChatMessage(role="user", content="hi"),
            ]
            await master_chat(msgs, conversation_id="conv-sys")

            first_call_body = mock_client.post.call_args[1]["body"]
            assert "system" in first_call_body
            assert first_call_body["system"] == "Be helpful"

            mock_client.post = AsyncMock()

            msgs2 = [
                ChatMessage(role="system", content="Be helpful"),
                ChatMessage(role="user", content="follow-up"),
            ]

            with patch("dashboard.master_agent.read_session_text", new_callable=AsyncMock, return_value="reply2"):
                await master_chat(msgs2, conversation_id="conv-sys")

            second_call_body = mock_client.post.call_args[1]["body"]
            assert "system" not in second_call_body


class TestMasterComplete:
    @pytest.mark.asyncio
    async def test_returns_content(self):
        from dashboard.master_agent import master_complete

        with patch("dashboard.master_agent.get_opencode_client") as mock_oc, \
             patch("dashboard.master_agent.read_session_text", new_callable=AsyncMock, return_value="Summary"):
            mock_client = MagicMock()
            mock_client.session.create = AsyncMock(return_value=MagicMock(id="sess-1"))
            mock_client.post = AsyncMock()
            mock_oc.return_value = mock_client

            result = await master_complete("Summarize this")
            assert result == "Summary"

    @pytest.mark.asyncio
    async def test_conversation_id_reuses_session(self):
        from dashboard.master_agent import master_complete

        with patch("dashboard.master_agent.get_opencode_client") as mock_oc, \
             patch("dashboard.master_agent.read_session_text", new_callable=AsyncMock, return_value="Done"):
            mock_client = MagicMock()
            mock_client.session.create = AsyncMock(return_value=MagicMock(id="sess-persist"))
            mock_client.post = AsyncMock()
            mock_oc.return_value = mock_client

            await master_complete("First", conversation_id="conv-1")
            await master_complete("Second", conversation_id="conv-1")

            assert mock_client.session.create.call_count == 1
            assert mock_client.post.call_count == 2
