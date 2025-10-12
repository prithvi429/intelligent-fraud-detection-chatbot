"""
Tools Unit Tests
----------------
Tests `chatbot/tools/`: API logic, parsing, Pinecone fallback, and formatting.
Each test mocks external systems (HTTP, Pinecone, OpenAI).

Covers:
- ✅ submit_and_score
- ✅ explain_alarms
- ✅ retrieve_guidance
- ✅ qa_handler
Run:
    pytest chatbot/tests/test_tools.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
import responses
from chatbot.tools.submit_and_score import submit_and_score
from chatbot.tools.explain_alarms import explain_alarms
from chatbot.tools.retrieve_guidance import retrieve_guidance
from chatbot.tools.qa_handler import qa_handler


# ============================================================
# 🧾 submit_and_score TOOL TESTS
# ============================================================
class TestSubmitAndScore:
    """Tests for the claim scoring tool."""

    def test_submit_and_score_valid_query(self, mock_api_responses):
        """✅ Valid query triggers API call and formats claim analysis."""
        query = "Score $15,000 accident in LA, reported 10 days late, provider shady_clinic"
        result = submit_and_score.run(query)

        assert "Claim Analysis: Reject" in result
        assert "Fraud Probability: 75.0%" in result
        assert "high_amount" in result
        assert "**Explanation:** High risk detected." in result

    def test_submit_and_score_no_amount(self, mock_api_responses):
        """⚠️ Missing amount → user guidance message."""
        query = "Score accident in LA, no amount"
        result = submit_and_score.run(query)
        assert "Could not parse a valid claim amount" in result

    def test_submit_and_score_api_error(self):
        """❌ API 500 → graceful fallback."""
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.POST,
                "http://test-backend.com/api/v1/score_claim",
                status=500
            )
            result = submit_and_score.run("Score $5000 claim")
            assert "couldn't score the claim right now" in result

    @patch("chatbot.utils.logger.log_tool_call")
    def test_submit_and_score_logging(self, mock_log, mock_api_responses):
        """🪵 Verifies proper logging of tool calls."""
        submit_and_score.run("Test query")
        mock_log.assert_called_once()


# ============================================================
# 🚨 explain_alarms TOOL TESTS
# ============================================================
class TestExplainAlarms:
    """Tests for explain_alarms (fraud alarm explanations)."""

    def test_explain_alarms_valid_type(self, mock_api_responses):
        """✅ Returns proper alarm explanation."""
        query = "Explain high_amount"
        result = explain_alarms.run(query)

        assert "Explanation for High Amount Alarm (HIGH Severity)" in result
        assert "Amount over $10k" in result
        assert "How to Resolve: Provide proof" in result

    def test_explain_alarms_fuzzy_match(self, mock_api_responses):
        """🧠 Fuzzy mapping → converts phrases to alarm codes."""
        query = "What is late reporting?"
        result = explain_alarms.run(query)

        # Even though API mock points to high_amount, extraction must occur
        assert isinstance(result, str)
        assert any(
            phrase in result for phrase in ["Explain", "Alarm", "Severity"]
        )

    def test_explain_alarms_unknown_type(self, mock_api_responses):
        """⚠️ Unknown alarm → returns supported list."""
        query = "Explain invalid_alarm"
        result = explain_alarms.run(query)
        assert "Supported alarms include:" in result

    def test_explain_alarms_api_error(self):
        """❌ API 404 → fallback user message."""
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                "http://test-backend.com/api/v1/explain/unknown",
                status=404
            )
            result = explain_alarms.run("Explain unknown")
            assert "couldn't fetch details" in result


# ============================================================
# 📖 retrieve_guidance TOOL TESTS
# ============================================================
class TestRetrieveGuidance:
    """Tests for retrieve_guidance (RAG policy guidance)."""

    def test_retrieve_guidance_pinecone_success(self, mock_settings, mock_pinecone):
        """✅ Pinecone returns valid match."""
        mock_settings.PINECONE_ENABLED = True
        result = retrieve_guidance.run("What docs?")
        assert "Guidance for 'What docs?'" in result
        assert "Test guidance" in result
        assert "Confidence: 95.0%" in result

    def test_retrieve_guidance_low_score_fallback(self, mock_settings, mock_pinecone):
        """⚠️ Low similarity score → DB fallback."""
        mock_pinecone.query.return_value.matches = [MagicMock(score=0.5)]
        mock_settings.PINECONE_ENABLED = True
        with patch("chatbot.tools.retrieve_guidance._fallback_to_db") as mock_fallback:
            retrieve_guidance.run("Low match query")
            mock_fallback.assert_called_once_with("Low match query")

    def test_retrieve_guidance_no_pinecone(self, mock_api_responses):
        """🧩 Pinecone disabled → direct DB search."""
        with patch("chatbot.config.settings.settings.PINECONE_ENABLED", False):
            result = retrieve_guidance.run("What docs?")
            assert "**Policy Guidance**" in result
            assert "Submit ID." in result
            assert "Match Confidence: 85.0%" in result

    def test_retrieve_guidance_pinecone_error(self, mock_settings):
        """❌ Pinecone failure → fallback."""
        mock_settings.PINECONE_ENABLED = True
        with patch("pinecone.init", side_effect=Exception("Pinecone down")), \
             patch("chatbot.tools.retrieve_guidance._fallback_to_db") as mock_fallback:
            retrieve_guidance.run("Error query")
            mock_fallback.assert_called_once()


# ============================================================
# 💬 qa_handler TOOL TESTS
# ============================================================
class TestQAHandler:
    """Tests for qa_handler (rejection + guidance combo)."""

    @patch("chatbot.tools.qa_handler.explain_alarms")
    @patch("chatbot.tools.qa_handler.retrieve_guidance")
    def test_qa_handler_success(self, mock_guidance, mock_explain):
        """✅ Combines both tools for rejection explanation."""
        mock_guidance.return_value = "Appeal within 30 days."
        mock_explain.return_value = "Late reporting means..."

        result = qa_handler.run("Why was my claim rejected due to late reporting?")
        assert "Late reporting means..." in result
        assert "Appeal within 30 days." in result
        mock_explain.assert_called_once_with("Why was my claim rejected due to late reporting?")
        mock_guidance.assert_called_once_with("Why was my claim rejected due to late reporting?")

    @patch("chatbot.tools.qa_handler.explain_alarms")
    def test_qa_handler_no_alarm(self, mock_explain):
        """⚙️ No alarm found → uses general guidance fallback."""
        mock_explain.return_value = "No specific alarm found."
        result = qa_handler.run("Why rejected?")
        assert "General rejection reasons" in result
        mock_explain.assert_called_once()

    def test_qa_handler_error(self):
        """❌ Error → returns empathetic fallback."""
        with patch("chatbot.tools.qa_handler.explain_alarms", side_effect=Exception("Tool error")):
            result = qa_handler.run("Error query")
            assert "I'm sorry" in result
            assert "couldn't retrieve details" in result
