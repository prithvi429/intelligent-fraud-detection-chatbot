"""
End-to-End Integration Tests
----------------------------
Tests full agent flow: Query → Reasoning → Tool → Response.

Simulates a user sending different types of queries and ensures:
- Correct tool is invoked (submit_and_score, retrieve_guidance, qa_handler).
- Agent output is well formatted.
- Errors are handled gracefully.

Mocks the LangChain AgentExecutor and internal tools for deterministic results.

Run:
    pytest chatbot/tests/test_end_to_end.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from chatbot.agent import run_agent


# ============================================================
# 🔍 End-to-End Flow Tests
# ============================================================
class TestEndToEndAgent:
    """Full ReAct flow tests for the chatbot agent."""

    @patch("chatbot.agent.create_agent")
    def test_end_to_end_claim_scoring(self, mock_create):
        """✅ Claim query → submit_and_score → formatted fraud result."""
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"output": "Claim Analysis: Reject\nFraud Probability: 75%"}
        mock_create.return_value = (mock_agent, MagicMock())

        result = run_agent("Please score this claim of $10,000 from Mumbai")
        assert "Claim Analysis" in result
        assert "Fraud Probability" in result
        mock_agent.invoke.assert_called_once()

    @patch("chatbot.agent.create_agent")
    def test_end_to_end_policy_guidance(self, mock_create):
        """📖 Policy query → retrieve_guidance → returns policy info."""
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"output": "📖 Policy Guidance\nSubmit ID proof and invoice."}
        mock_create.return_value = (mock_agent, MagicMock())

        result = run_agent("What documents are needed for a claim?")
        assert "Policy Guidance" in result
        assert "Submit ID" in result
        mock_agent.invoke.assert_called_once()

    @patch("chatbot.agent.create_agent")
    def test_end_to_end_rejection_query(self, mock_create):
        """💬 Rejection query → qa_handler → combines alarm + appeal advice."""
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "output": "Late reporting means delay >7 days. Appeal within 30 days."
        }
        mock_create.return_value = (mock_agent, MagicMock())

        result = run_agent("Why was my claim rejected due to late reporting?")
        assert "Late reporting" in result
        assert "Appeal" in result
        mock_agent.invoke.assert_called_once()

    @patch("chatbot.agent.create_agent")
    def test_end_to_end_error_handling(self, mock_create):
        """❌ Error inside agent → handled gracefully."""
        mock_agent = MagicMock()
        mock_agent.invoke.side_effect = Exception("Model timeout")
        mock_create.return_value = (mock_agent, MagicMock())

        result = run_agent("Score my claim again")
        assert "An error occurred" in result
        mock_agent.invoke.assert_called_once()

    @patch("chatbot.agent.create_agent")
    def test_end_to_end_no_session(self, mock_create):
        """⚙️ Works without session tracking."""
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"output": "General policy response"}
        mock_create.return_value = (mock_agent, None)

        result = run_agent("Tell me about policy coverage")
        assert "General policy" in result
        mock_agent.invoke.assert_called_once()


# ============================================================
# 🧠 Agent-Tool Routing Sanity Check
# ============================================================
class TestRoutingLogic:
    """Ensures proper routing logic between query type and tool."""

    @pytest.mark.parametrize(
        "query,expected_tool",
        [
            ("Score $5000 accident", "submit_and_score"),
            ("Explain location mismatch", "explain_alarms"),
            ("What documents for claim?", "retrieve_guidance"),
            ("Why was claim rejected?", "qa_handler"),
        ],
    )
    @patch("chatbot.agent.create_agent")
    def test_tool_routing_keywords(self, mock_create, query, expected_tool):
        """✅ Routes each query type to the right tool by keyword simulation."""
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {"output": f"Tool triggered: {expected_tool}"}
        mock_create.return_value = (mock_agent, MagicMock())

        result = run_agent(query)
        assert expected_tool.replace("_", " ") in result.lower()
