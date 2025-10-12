"""
Agent Unit Tests
----------------
Tests `agent.py`: agent creation, prompt loading, tool routing, and invocation.

Focus:
- Ensures ReAct agent loads tools and LLM correctly.
- Verifies `run_agent()` formats and logs correctly.
- Uses shared fixtures for mocks (LLM, settings, session, etc.)
Run:
    pytest chatbot/tests/test_agent.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from chatbot.agent import create_agent, run_agent, load_prompt
from chatbot.utils.session_manager import SessionManager


# ============================================================
# 🔧 TEST: Agent Creation and Setup
# ============================================================
class TestAgentCreation:
    """Verify agent and session initialization."""

    def test_create_agent_success(self, mock_settings, mock_llm):
        """✅ Creates agent successfully with valid session and LLM."""
        agent_executor, session = create_agent("test_session")

        assert agent_executor is not None
        assert isinstance(session, SessionManager)

        mock_llm.assert_called_once_with(
            model="gpt-3.5-turbo",
            temperature=0.1,
            openai_api_key="fake_key",
            max_tokens=4000
        )

    def test_create_agent_no_session(self, mock_settings, mock_llm):
        """✅ Works even when no session ID is provided."""
        agent, session = create_agent()
        assert agent is not None
        assert session is None

    def test_load_prompt_success(self, tmp_path):
        """✅ Loads prompt from file successfully."""
        temp_file = tmp_path / "test_prompt.md"
        temp_file.write_text("You are FraudBot - test prompt", encoding="utf-8")

        prompt = load_prompt(str(temp_file))
        assert "FraudBot" in prompt

    def test_load_prompt_missing_file(self):
        """❌ Missing file → raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent_file.md")


# ============================================================
# 🧠 TEST: run_agent() Behavior
# ============================================================
class TestRunAgent:
    """Unit tests for `run_agent()`."""

    @patch("chatbot.agent.create_agent")
    @patch("chatbot.utils.formatter.format_chat_response")
    def test_run_agent_success(self, mock_format, mock_create, mock_session):
        """✅ Runs successfully — adds to session, formats output."""
        mock_agent, mock_sess = MagicMock(), MagicMock()
        mock_create.return_value = mock_agent, mock_sess
        mock_agent.invoke.return_value = {"output": "Test response"}
        mock_format.return_value = "Formatted"

        result = run_agent("Test query", "test_id")

        assert result == "Formatted"
        mock_agent.invoke.assert_called_once_with({"input": "Test query"})
        mock_sess.add_message.assert_any_call("human", "Test query")
        mock_sess.add_message.assert_any_call("ai", "Formatted")

    @patch("chatbot.agent.create_agent")
    def test_run_agent_error(self, mock_create, mock_session):
        """⚠️ Handles agent/LLM exceptions gracefully and logs error."""
        mock_agent, _ = MagicMock(), MagicMock()
        mock_create.return_value = mock_agent, None
        mock_agent.invoke.side_effect = Exception("LLM error")

        with patch("chatbot.agent.logger") as mock_logger:
            result = run_agent("Error query")
            assert "An error occurred" in result
            mock_logger.error.assert_called_once()

    @patch("chatbot.agent.create_agent")
    def test_run_agent_no_session(self, mock_create):
        """✅ Still works without session (stateless)."""
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"output": "No session response"}
        mock_create.return_value = mock_agent, None

        result = run_agent("Query")
        assert "No session response" in result


# ============================================================
# 🧩 TEST: REPL Mode (manual optional)
# ============================================================
class TestREPL:
    """Manual REPL mode test placeholder."""
    # Optional: mock input/output streams if you automate REPL testing.
    pass
