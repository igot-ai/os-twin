import sys
import os
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# Add dashboard dir to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dashboard.agent_bridge import ask_agent

class TestAgentBridge(unittest.IsolatedAsyncioTestCase):
    @patch("dashboard.agent_bridge.get_plans_context", new_callable=AsyncMock)
    @patch("dashboard.agent_bridge.get_rooms_context", new_callable=AsyncMock)
    @patch("dashboard.agent_bridge.get_stats_context", new_callable=AsyncMock)
    @patch("dashboard.agent_bridge.search_memory_context", new_callable=AsyncMock)
    @patch("os.environ.get")
    async def test_ask_agent_no_key(self, mock_env, mock_search, mock_stats, mock_rooms, mock_plans):
        mock_env.return_value = None
        mock_plans.return_value = "Plan A"
        mock_rooms.return_value = "Room 1"
        mock_stats.return_value = "Stats"
        mock_search.return_value = "Search"
        
        with patch("pathlib.Path.exists", return_value=False):
            answer = await ask_agent("What's the status?", platform="generic")
            self.assertIn("No AI API key found", answer)

    @patch("dashboard.agent_bridge.get_plans_context", new_callable=AsyncMock)
    @patch("dashboard.agent_bridge.get_rooms_context", new_callable=AsyncMock)
    @patch("dashboard.agent_bridge.get_stats_context", new_callable=AsyncMock)
    @patch("dashboard.agent_bridge.search_memory_context", new_callable=AsyncMock)
    @patch("os.environ.get")
    @patch("langchain_google_genai.ChatGoogleGenerativeAI")
    async def test_ask_agent_gemini(self, mock_llm_class, mock_env, mock_search, mock_stats, mock_rooms, mock_plans):
        mock_env.side_effect = lambda k: "fake_key" if k == "GOOGLE_API_KEY" else None
        mock_plans.return_value = "Plan A"
        mock_rooms.return_value = "Room 1"
        mock_stats.return_value = "Stats"
        mock_search.return_value = "Search"
        
        # Mock LLM response
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="The status is green."))
        mock_llm_class.return_value = mock_llm
        
        answer = await ask_agent("What's the status?", platform="telegram")
        self.assertEqual(answer, "The status is green.")
        mock_llm.ainvoke.assert_called_once()

if __name__ == "__main__":
    unittest.main()
