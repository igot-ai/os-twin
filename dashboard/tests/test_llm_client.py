"""
Unit tests for llm_client.py multi-provider LLM abstraction.
"""

import asyncio
import json
import pytest
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

# Mock google.genai before importing llm_client
mock_google_genai = MagicMock()
mock_google_types = MagicMock()
sys.modules["google.genai"] = mock_google_genai
sys.modules["google.genai.types"] = mock_google_types

from dashboard.llm_client import (
    ToolCall,
    ChatMessage,
    LLMClient,
    LLMConfig,
    LLMError,
    OpenAIClient,
    GoogleClient,
    create_client,
    _detect_provider_from_model,
    _get_base_url,
    load_provider_urls,
    PROVIDER_URLS,
)


class TestToolCall:
    def test_tool_call_repr(self):
        tc = ToolCall(id="call_123", name="get_weather", arguments={"city": "London"})
        assert repr(tc) == "ToolCall(id='call_123', name='get_weather')"

    def test_tool_call_default_arguments(self):
        tc = ToolCall(id="call_456", name="search")
        assert tc.arguments == {}


class TestChatMessage:
    def test_chat_message_repr(self):
        msg = ChatMessage(role="user", content="Hello world!")
        assert "ChatMessage" in repr(msg)
        assert "user" in repr(msg)

    def test_chat_message_with_tool_calls(self):
        tc = ToolCall(id="tc1", name="test_tool", arguments={"x": 1})
        msg = ChatMessage(role="assistant", content="Result", tool_calls=[tc])
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "test_tool"

    def test_chat_message_tool_response(self):
        msg = ChatMessage(
            role="tool",
            content="Tool result",
            tool_call_id="tc_123",
            name="get_weather"
        )
        assert msg.role == "tool"
        assert msg.tool_call_id == "tc_123"
        assert msg.name == "get_weather"


class TestLLMConfig:
    def test_default_config(self):
        config = LLMConfig()
        assert config.max_tokens == 4096
        assert config.temperature is None
        assert config.top_p is None
        assert config.stop is None

    def test_custom_config(self):
        config = LLMConfig(max_tokens=8192, temperature=0.7, stop=["END"])
        assert config.max_tokens == 8192
        assert config.temperature == 0.7
        assert config.stop == ["END"]


class TestDetectProviderFromModel:
    def test_openai_models(self):
        assert _detect_provider_from_model("gpt-4") == "openai"
        assert _detect_provider_from_model("gpt-3.5-turbo") == "openai"
        assert _detect_provider_from_model("o1-preview") == "openai"
        assert _detect_provider_from_model("o3-mini") == "openai"
        assert _detect_provider_from_model("O4-MINI") == "openai"

    def test_anthropic_models(self):
        assert _detect_provider_from_model("claude-3-opus") == "anthropic"
        assert _detect_provider_from_model("claude-sonnet-4") == "anthropic"
        assert _detect_provider_from_model("CLAUDE-3-HAIKU") == "anthropic"

    def test_google_models(self):
        assert _detect_provider_from_model("gemini-pro") == "google"
        assert _detect_provider_from_model("gemini-2-flash") == "google"
        assert _detect_provider_from_model("GEMINI-ULTRA") == "google"

    def test_deepseek_models(self):
        assert _detect_provider_from_model("deepseek-coder") == "deepseek"
        assert _detect_provider_from_model("deepseek-chat") == "deepseek"

    def test_mistral_models(self):
        assert _detect_provider_from_model("mistral-large") == "mistral"
        assert _detect_provider_from_model("mixtral-8x7b") == "mistral"

    def test_llama_models(self):
        provider = _detect_provider_from_model("llama-3-70b")
        assert provider in ["together", "fireworks", "groq", "deepinfra"]

    def test_unknown_model_defaults_to_openai(self):
        assert _detect_provider_from_model("unknown-model") == "openai"


class TestGetBaseUrl:
    def test_hardcoded_providers(self):
        assert _get_base_url("openai") == "https://api.openai.com/v1"
        assert _get_base_url("anthropic") == "https://api.anthropic.com/v1"
        assert _get_base_url("deepseek") == "https://api.deepseek.com"

    def test_provider_from_urls_json(self):
        if "xai" in PROVIDER_URLS:
            assert _get_base_url("xai") == PROVIDER_URLS["xai"]["base"]

    def test_unknown_provider(self):
        assert _get_base_url("unknown_provider_xyz") is None


class TestLoadProviderUrls:
    def test_loads_valid_json(self):
        urls = load_provider_urls()
        assert isinstance(urls, dict)
        assert "openai" in urls
        assert urls["openai"]["base"] == "https://api.openai.com/v1"


class TestOpenAIClient:
    def test_init(self):
        with patch("openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value = MagicMock()
            client = OpenAIClient(model="gpt-4", api_key="test-key")
            assert client.model == "gpt-4"

    def test_convert_messages_simple(self):
        with patch("openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value = MagicMock()
            client = OpenAIClient(model="gpt-4", api_key="test")
            messages = [
                ChatMessage(role="system", content="You are helpful."),
                ChatMessage(role="user", content="Hello"),
            ]
            converted = client._convert_messages(messages)
            assert len(converted) == 2
            assert converted[0]["role"] == "system"
            assert converted[1]["role"] == "user"

    def test_convert_messages_with_tool_response(self):
        with patch("openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value = MagicMock()
            client = OpenAIClient(model="gpt-4", api_key="test")
            messages = [
                ChatMessage(role="assistant", content="Let me check.", tool_calls=[
                    ToolCall(id="tc_1", name="get_weather", arguments={"city": "NYC"})
                ]),
                ChatMessage(role="tool", content="Sunny, 72F", tool_call_id="tc_1"),
            ]
            converted = client._convert_messages(messages)
            assert len(converted) == 2
            assert converted[1]["role"] == "tool"
            assert converted[1]["tool_call_id"] == "tc_1"
            assert converted[1]["content"] == "Sunny, 72F"

    def test_convert_tools(self):
        with patch("openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value = MagicMock()
            client = OpenAIClient(model="gpt-4", api_key="test")
            tools = [
                {"name": "get_weather", "description": "Get weather", "parameters": {}}
            ]
            converted = client._convert_tools(tools)
            assert len(converted) == 1
            assert converted[0]["type"] == "function"
            assert converted[0]["function"]["name"] == "get_weather"

    @pytest.mark.asyncio
    async def test_chat_with_mock(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello there!"
        mock_response.choices[0].message.role = "assistant"
        mock_response.choices[0].message.tool_calls = None

        with patch("openai.AsyncOpenAI") as MockAsyncOpenAI:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            MockAsyncOpenAI.return_value = mock_client

            client = OpenAIClient(model="gpt-4", api_key="test")
            messages = [ChatMessage(role="user", content="Hi")]
            result = await client.chat(messages)

            assert result.content == "Hello there!"
            assert result.role == "assistant"

    @pytest.mark.asyncio
    async def test_chat_with_tool_calls(self):
        mock_tc = MagicMock()
        mock_tc.id = "tc_123"
        mock_tc.function.name = "get_weather"
        mock_tc.function.arguments = '{"city": "London"}'

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.role = "assistant"
        mock_response.choices[0].message.tool_calls = [mock_tc]

        with patch("openai.AsyncOpenAI") as MockAsyncOpenAI:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            MockAsyncOpenAI.return_value = mock_client

            client = OpenAIClient(model="gpt-4", api_key="test")
            messages = [ChatMessage(role="user", content="What's the weather?")]
            result = await client.chat(messages)

            assert len(result.tool_calls) == 1
            assert result.tool_calls[0].name == "get_weather"
            assert result.tool_calls[0].arguments == {"city": "London"}

    @pytest.mark.asyncio
    async def test_chat_retry_on_failure(self):
        call_count = 0

        async def failing_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("API Error")
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Success"
            mock_response.choices[0].message.role = "assistant"
            mock_response.choices[0].message.tool_calls = None
            return mock_response

        with patch("openai.AsyncOpenAI") as MockAsyncOpenAI:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = failing_create
            MockAsyncOpenAI.return_value = mock_client

            client = OpenAIClient(model="gpt-4", api_key="test")
            messages = [ChatMessage(role="user", content="Hi")]
            result = await client.chat(messages)

            assert call_count == 3
            assert result.content == "Success"


class TestGoogleClient:
    def test_init(self):
        mock_client = MagicMock()
        with patch.object(mock_google_genai, "Client", return_value=mock_client):
            client = GoogleClient(model="gemini-pro", api_key="test-key")
            assert client.model == "gemini-pro"

    def test_convert_messages_simple(self):
        mock_types = MagicMock()
        mock_content = MagicMock()
        mock_part = MagicMock()
        mock_types.Content = mock_content
        mock_types.Part = mock_part
        
        with patch.object(mock_google_genai, "types", mock_types):
            with patch.object(mock_google_genai, "Client"):
                client = GoogleClient(model="gemini-pro", api_key="test")
                messages = [
                    ChatMessage(role="system", content="You are helpful."),
                    ChatMessage(role="user", content="Hello"),
                ]
                converted = client._convert_messages(messages)
                assert len(converted) == 2

    def test_convert_messages_with_tool_response(self):
        mock_types = MagicMock()
        mock_types.Content = MagicMock(return_value=MagicMock())
        mock_types.Part = MagicMock()
        mock_types.FunctionResponse = MagicMock(return_value=MagicMock())
        
        with patch.object(mock_google_genai, "types", mock_types):
            with patch.object(mock_google_genai, "Client"):
                client = GoogleClient(model="gemini-pro", api_key="test")
                messages = [
                    ChatMessage(
                        role="tool",
                        content="72F, Sunny",
                        tool_call_id="fc_get_weather",
                        name="get_weather"
                    ),
                ]
                converted = client._convert_messages(messages)
                assert len(converted) == 1

    def test_convert_messages_tool_response_extracts_name_from_id(self):
        mock_types = MagicMock()
        mock_types.Content = MagicMock(return_value=MagicMock())
        mock_types.Part = MagicMock()
        mock_types.FunctionResponse = MagicMock(return_value=MagicMock())
        
        with patch.object(mock_google_genai, "types", mock_types):
            with patch.object(mock_google_genai, "Client"):
                client = GoogleClient(model="gemini-pro", api_key="test")
                messages = [
                    ChatMessage(
                        role="tool",
                        content="Result",
                        tool_call_id="fc_search_docs"
                    ),
                ]
                converted = client._convert_messages(messages)
                assert len(converted) == 1

    def test_convert_tools(self):
        mock_types = MagicMock()
        mock_types.FunctionDeclaration = MagicMock(return_value=MagicMock())
        mock_types.Tool = MagicMock(return_value=MagicMock())
        
        with patch.object(mock_google_genai, "types", mock_types):
            with patch.object(mock_google_genai, "Client"):
                client = GoogleClient(model="gemini-pro", api_key="test")
                tools = [
                    {"name": "search", "description": "Search the web", "parameters": {}}
                ]
                converted = client._convert_tools(tools)
                assert converted is not None

    @pytest.mark.asyncio
    async def test_chat_with_mock(self):
        mock_response = MagicMock()
        mock_response.text = "Hello from Gemini!"
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [MagicMock()]
        mock_response.candidates[0].content.parts[0].text = "Hello from Gemini!"
        mock_response.candidates[0].content.parts[0].function_call = None

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch.object(mock_google_genai, "Client", return_value=mock_client):
            client = GoogleClient(model="gemini-pro", api_key="test")
            messages = [ChatMessage(role="user", content="Hi")]
            result = await client.chat(messages)

            assert result.content == "Hello from Gemini!"

    @pytest.mark.asyncio
    async def test_chat_with_tool_calls(self):
        mock_fc = MagicMock()
        mock_fc.name = "get_weather"
        mock_fc.args = {"city": "Tokyo"}

        mock_part = MagicMock()
        mock_part.text = None
        mock_part.function_call = mock_fc

        mock_response = MagicMock()
        mock_response.text = None
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [mock_part]

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch.object(mock_google_genai, "Client", return_value=mock_client):
            client = GoogleClient(model="gemini-pro", api_key="test")
            messages = [ChatMessage(role="user", content="Weather?")]
            result = await client.chat(messages)

            assert len(result.tool_calls) == 1
            assert result.tool_calls[0].name == "get_weather"
            assert result.tool_calls[0].arguments == {"city": "Tokyo"}


class TestCreateClient:
    def test_create_openai_client(self):
        with patch("openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value = MagicMock()
            client = create_client("gpt-4", provider="openai", api_key="test")
            assert isinstance(client, OpenAIClient)

    def test_create_google_client(self):
        mock_client = MagicMock()
        with patch.object(mock_google_genai, "Client", return_value=mock_client):
            client = create_client("gemini-pro", provider="google", api_key="test")
            assert isinstance(client, GoogleClient)

    def test_create_client_with_provider_prefix(self):
        with patch("openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value = MagicMock()
            client = create_client("anthropic:claude-3-opus", api_key="test")
            assert isinstance(client, OpenAIClient)

    def test_create_client_with_slash_prefix(self):
        mock_client = MagicMock()
        with patch.object(mock_google_genai, "Client", return_value=mock_client):
            client = create_client("google/gemini-pro", api_key="test")
            assert isinstance(client, GoogleClient)

    def test_create_client_auto_detect(self):
        with patch("openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value = MagicMock()
            client = create_client("claude-3-opus", api_key="test")
            assert isinstance(client, OpenAIClient)

        mock_client = MagicMock()
        with patch.object(mock_google_genai, "Client", return_value=mock_client):
            client = create_client("gemini-pro", api_key="test")
            assert isinstance(client, GoogleClient)


class TestLLMError:
    def test_llm_error_message(self):
        error = LLMError("API failed", provider="openai")
        assert str(error) == "API failed"
        assert error.provider == "openai"

    def test_llm_error_with_original(self):
        original = ValueError("Original error")
        error = LLMError("Wrapped", provider="google", original_error=original)
        assert error.original_error == original


class TestProviderUrlsIntegration:
    def test_provider_urls_contains_expected_providers(self):
        expected = ["openai", "anthropic", "google", "deepseek", "mistral", "groq"]
        for provider in expected:
            assert provider in PROVIDER_URLS, f"Missing {provider} in provider_urls.json"

    def test_provider_urls_has_base_url(self):
        for provider, config in PROVIDER_URLS.items():
            assert "base" in config, f"Missing base URL for {provider}"


class TestTruncateMessagesThinWrapper:
    def test_returns_unchanged_when_no_context(self):
        with patch("openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value = MagicMock()
            client = OpenAIClient(model="gpt-4", api_key="test")

        with patch("dashboard.lib.settings.models_dev_loader.truncate_messages_for_model", return_value=[{"role": "user", "content": "hi"}]):
            with patch("dashboard.lib.settings.models_dev_loader.get_context_limit", return_value=(0, 0)):
                msgs = [ChatMessage(role="user", content="hi")]
                result = client._truncate_messages(msgs)
        assert len(result) == 1
        assert result[0].content == "hi"

    def test_preserves_chat_message_fields_on_truncation(self):
        with patch("openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value = MagicMock()
            client = OpenAIClient(model="gpt-4", api_key="test", provider="openai")

        original = ChatMessage(
            role="assistant",
            content="long content that will be trimmed",
            tool_calls=[ToolCall(id="tc1", name="fn", arguments={"a": 1})],
            tool_call_id="tc1",
            name="fn",
            thought_signature="sig",
            images=["http://img.png"],
        )
        truncated_dicts = [{"role": "assistant", "content": "long content"}]

        with patch("dashboard.lib.settings.models_dev_loader.truncate_messages_for_model", return_value=truncated_dicts):
            result = client._truncate_messages([original])
        assert result[0].content == "long content"
        assert len(result[0].tool_calls) == 1
        assert result[0].tool_call_id == "tc1"
        assert result[0].name == "fn"
        assert result[0].thought_signature == "sig"
        assert result[0].images == ["http://img.png"]

    def test_returns_same_objects_when_no_change(self):
        with patch("openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value = MagicMock()
            client = OpenAIClient(model="gpt-4", api_key="test")

        msg = ChatMessage(role="user", content="short")
        with patch("dashboard.lib.settings.models_dev_loader.truncate_messages_for_model", return_value=[{"role": "user", "content": "short"}]):
            result = client._truncate_messages([msg])
        assert result[0] is msg

    def test_exception_returns_original_messages(self):
        with patch("openai.AsyncOpenAI") as MockAsyncOpenAI:
            MockAsyncOpenAI.return_value = MagicMock()
            client = OpenAIClient(model="gpt-4", api_key="test")

        msgs = [ChatMessage(role="user", content="hello")]
        with patch("dashboard.lib.settings.models_dev_loader.truncate_messages_for_model", side_effect=RuntimeError("boom")):
            result = client._truncate_messages(msgs)
        assert result == msgs
