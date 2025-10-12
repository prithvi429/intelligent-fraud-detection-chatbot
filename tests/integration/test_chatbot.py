"""
Integration Tests: Chatbot Layer
--------------------------------
Tests LangChain tools calling the fraud detection API.
Validates:
- submit_and_score → calls API and returns formatted results
- explain_alarms → retrieves alarm details
- retrieve_guidance → queries Pinecone or DB for guidance
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from src.main import app

# LangChain tools (assumed implemented)
from src.chatbot.tools import submit_and_score, explain_alarms, retrieve_guidance
from src.chatbot.agent import create_agent


# =========================================================
# 📦 Fixtures
# =========================================================
@pytest.fixture
def mock_openai():
    """Mock OpenAI LLM with static response for all prompts."""
    mock_llm = Mock()
    mock_llm.invoke.return_value = "Mock response: Claim scored as high risk."
    with patch("langchain_openai.ChatOpenAI", return_value=mock_llm):
        yield mock_llm


@pytest.fixture
def mock_pinecone():
    """Mock Pinecone client used in retrieve_guidance."""
    mock_index = Mock()
    mock_index.query.return_value = {
        "matches": [
            {
                "score": 0.9,
                "metadata": {
                    "query": "docs needed",
                    "response": "Please provide ID and invoice."
                },
            }
        ]
    }
    with patch("pinecone_grpc.Pinecone") as mock_pc:
        mock_pc.return_value.Index.return_value = mock_index
        yield mock_index


@pytest.fixture
def test_app():
    """FastAPI TestClient (for API simulation)."""
    with TestClient(app) as client:
        yield client


# =========================================================
# 🤖 Test Suite: Chatbot Tools
# =========================================================
class TestChatbotIntegration:
    """Integration tests for chatbot-level LangChain tools."""

    @pytest.mark.usefixtures("mock_openai", "mock_pinecone", "mock_db", "override_get_db")
    def test_submit_and_score_tool_integration(self):
        """Test submit_and_score: parses input, calls API, returns structured output."""
        user_input = (
            "Score claim: amount 15000, delay 10 days, provider shady_clinic, "
            "notes staged accident quick cash, claimant user1, location LA, new bank yes"
        )

        mock_response = {
            "fraud_probability": 75.0,
            "alarms": [{"type": "high_amount", "description": "Exceeds threshold"}],
            "decision": "Reject",
            "explanation": "High risk claim with multiple alarms."
        }

        with patch("requests.post", return_value=Mock(status_code=200, json=lambda: mock_response)):
            result = submit_and_score(user_input)

        # Verify output
        assert isinstance(result, (dict, str))
        if isinstance(result, dict):
            assert result["fraud_probability"] == 75.0
            assert "Reject" in result["decision"]
            assert any("high_amount" in str(alarm) for alarm in result["alarms"])
        else:
            assert "75" in result
            assert "reject" in result.lower()

    @pytest.mark.usefixtures("mock_openai", "mock_pinecone", "mock_db", "override_get_db")
    def test_explain_alarms_tool_integration(self):
        """Test explain_alarms tool → calls /explain/{type} and returns text."""
        alarm_type = "high_amount"

        valid_json = {
            "type": "high_amount",
            "description": "Amount exceeds the $10,000 limit.",
            "severity": "high"
        }

        with patch("requests.get", return_value=Mock(status_code=200, json=lambda: valid_json)):
            explanation = explain_alarms(alarm_type)

        assert isinstance(explanation, str)
        assert "exceeds" in explanation.lower()
        assert "high" in explanation.lower()

        # Invalid case (404)
        with patch("requests.get", return_value=Mock(status_code=404, json=lambda: {"detail": "Unknown alarm"})):
            invalid_exp = explain_alarms("invalid")
            assert "unknown" in invalid_exp.lower()

    @pytest.mark.usefixtures("mock_openai", "mock_pinecone", "mock_db", "override_get_db")
    def test_retrieve_guidance_tool_integration(self):
        """Test retrieve_guidance: calls Pinecone/DB → returns guidance dict."""
        query = "What documents are needed?"

        mock_guidance = {
            "query": query,
            "response": "Please submit your ID, insurance card, and accident report.",
            "required_docs": ["ID", "insurance card", "accident report"]
        }

        with patch(
            "src.chatbot.tools.retrieve_guidance.get_guidance_from_pinecone_or_db",
            return_value=(mock_guidance, 0.95)
        ):
            guidance = retrieve_guidance(query)

        assert isinstance(guidance, dict)
        assert "response" in guidance
        assert "ID" in guidance["required_docs"][0]
