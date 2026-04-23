"""Tests for the shared.ai gateway — completion, embedding, config, retry."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

# Ensure shared.ai is importable
_agents_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..")
if _agents_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_agents_dir))

from shared.ai.errors import AIError, AIAuthError, AITimeoutError
from shared.ai.retry import with_retry
from shared.ai.config import AIConfig, reset_config


class TestAIConfig(unittest.TestCase):
    def setUp(self):
        reset_config()

    def tearDown(self):
        reset_config()

    @patch.dict(
        os.environ,
        {"GOOGLE_CLOUD_PROJECT": "test-project", "VERTEX_LOCATION": "us-central1"},
        clear=False,
    )
    def test_env_fallback_creates_vertex_config(self):
        from shared.ai.config import _load_from_env

        cfg = _load_from_env()
        self.assertEqual(cfg.provider, "vertex_ai")
        self.assertEqual(cfg.vertex_project, "test-project")
        self.assertEqual(cfg.vertex_location, "us-central1")

    @patch.dict(os.environ, {}, clear=True)
    def test_env_fallback_without_project_uses_gemini(self):
        # Remove GOOGLE_CLOUD_PROJECT if present
        os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
        from shared.ai.config import _load_from_env

        cfg = _load_from_env()
        self.assertEqual(cfg.provider, "gemini")

    def test_full_model_with_purpose(self):
        cfg = AIConfig(
            provider="vertex_ai",
            completion_model="gemini-3-flash",
            knowledge_model="vertex_ai/claude-sonnet-4-5",
            memory_model="vertex_ai/gemini-3-flash",
        )
        self.assertEqual(cfg.full_model(), "vertex_ai/gemini-3-flash")
        self.assertEqual(cfg.full_model("knowledge"), "vertex_ai/claude-sonnet-4-5")
        self.assertEqual(cfg.full_model("memory"), "vertex_ai/gemini-3-flash")

    def test_full_model_already_qualified(self):
        cfg = AIConfig(completion_model="vertex_ai/gemini-3-flash-preview")
        self.assertEqual(cfg.full_model(), "vertex_ai/gemini-3-flash-preview")

    def test_full_cloud_embedding_model(self):
        cfg = AIConfig(provider="vertex_ai", cloud_embedding_model="text-embedding-005")
        self.assertEqual(
            cfg.full_cloud_embedding_model(), "vertex_ai/text-embedding-005"
        )

    def test_reset_clears_cache(self):
        from shared.ai.config import get_config, reset_config

        # Force env fallback
        with patch(
            "shared.ai.config._load_from_settings", side_effect=Exception("no settings")
        ):
            c1 = get_config()
            reset_config()
            c2 = get_config()
            self.assertIsNot(c1, c2)


class TestRetry(unittest.TestCase):
    def test_retries_on_generic_error(self):
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient")
            return "success"

        result = with_retry(flaky, max_retries=3, base_delay=0.01)
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)

    def test_no_retry_on_auth_error(self):
        def auth_fail():
            raise AIAuthError("bad key")

        with self.assertRaises(AIAuthError):
            with_retry(auth_fail, max_retries=3)

    def test_no_retry_on_timeout_error(self):
        def timeout_fail():
            raise AITimeoutError("timed out")

        with self.assertRaises(AITimeoutError):
            with_retry(timeout_fail, max_retries=3)

    def test_raises_last_error_after_exhaustion(self):
        def always_fail():
            raise ValueError("always")

        with self.assertRaises(ValueError):
            with_retry(always_fail, max_retries=1, base_delay=0.01)


class TestCompletion(unittest.TestCase):
    def setUp(self):
        reset_config()

    def tearDown(self):
        reset_config()

    @patch("litellm.completion")
    @patch("shared.ai.config._load_from_settings", side_effect=Exception("no settings"))
    def test_get_completion_calls_litellm(self, _mock_settings, mock_litellm):
        mock_choice = MagicMock()
        mock_choice.message.content = "hello world"
        mock_choice.message.tool_calls = None
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage = None
        mock_litellm.return_value = mock_resp

        from shared.ai import get_completion

        result = get_completion("test prompt")

        self.assertEqual(result, "hello world")
        mock_litellm.assert_called_once()
        call_kwargs = mock_litellm.call_args.kwargs
        self.assertIn("gemini", call_kwargs["model"])

    @patch("litellm.completion")
    @patch("shared.ai.config._load_from_settings", side_effect=Exception("no settings"))
    def test_completion_with_tools_returns_tool_calls(
        self, _mock_settings, mock_litellm
    ):
        mock_tc = MagicMock()
        mock_tc.id = "call_1"
        mock_tc.function.name = "list_plans"
        mock_tc.function.arguments = '{"limit": 10}'
        mock_choice = MagicMock()
        mock_choice.message.content = ""
        mock_choice.message.tool_calls = [mock_tc]
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage = None
        mock_litellm.return_value = mock_resp

        from shared.ai import complete

        result = complete(
            "test", tools=[{"type": "function", "function": {"name": "list_plans"}}]
        )

        self.assertIsNotNone(result.tool_calls)
        self.assertEqual(result.tool_calls[0]["function"]["name"], "list_plans")

    @patch("litellm.completion")
    @patch("shared.ai.config._load_from_settings", side_effect=Exception("no settings"))
    def test_completion_with_purpose(self, _mock_settings, mock_litellm):
        mock_choice = MagicMock()
        mock_choice.message.content = "result"
        mock_choice.message.tool_calls = None
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage = None
        mock_litellm.return_value = mock_resp

        from shared.ai import get_completion
        from shared.ai.config import get_config

        cfg = get_config()
        cfg.knowledge_model = "vertex_ai/claude-sonnet-4-5"

        get_completion("test", purpose="knowledge")
        call_kwargs = mock_litellm.call_args.kwargs
        self.assertEqual(call_kwargs["model"], "vertex_ai/claude-sonnet-4-5")


class TestEmbedding(unittest.TestCase):
    @patch("sentence_transformers.SentenceTransformer")
    def test_local_embedding(self, mock_st_class):
        import numpy as np

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])
        mock_st_class.return_value = mock_model

        from shared.ai import get_embedding

        result = get_embedding(["test"], model="local/all-MiniLM-L6-v2")

        self.assertEqual(result, [[0.1, 0.2, 0.3]])
        mock_st_class.assert_called_once_with("all-MiniLM-L6-v2")

    @patch("litellm.embedding")
    def test_cloud_embedding(self, mock_litellm):
        mock_litellm.return_value.data = [{"embedding": [0.4, 0.5, 0.6]}]

        from shared.ai import get_embedding

        result = get_embedding(["test"], model="vertex_ai/text-embedding-005")

        self.assertEqual(result, [[0.4, 0.5, 0.6]])
        mock_litellm.assert_called_once()

    def test_empty_texts_returns_empty(self):
        from shared.ai import get_embedding

        self.assertEqual(get_embedding([]), [])

    @patch("sentence_transformers.SentenceTransformer")
    def test_local_model_cached(self, mock_st_class):
        import numpy as np

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2]])
        mock_st_class.return_value = mock_model

        from shared.ai.embedding import _local_models

        _local_models.clear()

        from shared.ai import get_embedding

        get_embedding(["a"], model="local/test-model")
        get_embedding(["b"], model="local/test-model")

        # SentenceTransformer should only be constructed once
        mock_st_class.assert_called_once_with("test-model")


class TestErrors(unittest.TestCase):
    def test_error_hierarchy(self):
        self.assertTrue(issubclass(AIAuthError, AIError))
        self.assertTrue(issubclass(AITimeoutError, AIError))

    def test_errors_are_catchable(self):
        with self.assertRaises(AIError):
            raise AIAuthError("test")


if __name__ == "__main__":
    unittest.main()
