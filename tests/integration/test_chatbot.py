"""
Integration Tests — Chatbot Layer
---------------------------------
Tests integration between LangChain tools and the fraud detection backend.

Validates:
- submit_and_score → Fraud scoring tool
- explain_alarm → Alarm explanation retrieval
- retrieve_guidance → Policy guidance (RAG retrieval)
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from src.main import app  # ✅ your main.py is at project root (not src.main)

# ✅ Direct imports from your chatbot package
from chatbot.tools import submit_and_score, explain_alarms, retrieve_guidance
from chatbot.agent import create_agent


# =========================================================
# 📦 Fixtures
# =========================================================
@pytest.fixture
def mock_openai():
    """Mock OpenAI LLM with deterministic responses."""
    mock_llm = Mock()
    mock_llm.invoke.return_value = "Mock response: Claim scored as high risk."
    with patch("langchain_openai.ChatOpenAI", return_value=mock_llm):
        yield mock_llm


@pytest.fixture
def mock_pinecone():
    """Mock Pinecone vector DB client used in retrieve_guidance."""
    mock_index = Mock()
    mock_index.query.return_value = {
        "matches": [
            {
                "score": 0.92,
                "metadata": {
                    "query": "docs needed",
                    "response": "Please submit ID and invoice for verification."
                },
            }
        ]
    }
    with patch("pinecone.Pinecone") as mock_pc:
        mock_pc.return_value.Index.return_value = mock_index
        yield mock_index


@pytest.fixture
def test_app():
    """Create a FastAPI TestClient."""
    with TestClient(app) as client:
        yield client


# =========================================================
# 🤖 Chatbot Integration Test Suite
# =========================================================
class TestChatbotIntegration:
    """Integration tests for all chatbot-level LangChain tools."""

    @pytest.mark.usefixtures("mock_openai", "mock_pinecone")
    def test_submit_and_score_tool_integration(self):
        """Test submit_and_score end-to-end behavior."""
        user_input = (
            "Score claim: amount 15000, delay 10 days, provider shady_clinic, "
            "notes staged accident quick cash, claimant user1, location LA, new bank yes"
        )

        mock_response = {
            "fraud_probability": 82.5,
            "alarms": [{"type": "high_amount", "description": "Exceeds threshold"}],
            "decision": "Reject",
            "explanation": "High risk claim with multiple suspicious indicators."
        }

        with patch("requests.post", return_value=Mock(status_code=200, json=lambda: mock_response)):
            result = submit_and_score(user_input)

        # ✅ Validation
        assert isinstance(result, (dict, str))
        if isinstance(result, dict):
            assert result["fraud_probability"] == 82.5
            assert "Reject" in result["decision"]
            assert any("high_amount" in str(alarm) for alarm in result["alarms"])
        else:
            assert "82" in result
            assert "reject" in result.lower()

    @pytest.mark.usefixtures("mock_openai", "mock_pinecone")
    def test_explain_alarm_tool_integration(self):
        """Test explain_alarm: retrieves description from backend."""
        alarm_type = "high_amount"

        valid_json = {
            "type": "high_amount",
            "description": "Amount exceeds the $10,000 threshold.",
            "severity": "high"
        }

        with patch("requests.get", return_value=Mock(status_code=200, json=lambda: valid_json)):
            explanation = explain_alarm(alarm_type)

        # ✅ Should return meaningful text
        assert isinstance(explanation, str)
        assert "exceeds" in explanation.lower()
        assert "high" in explanation.lower()

        # ❌ Invalid case
        with patch("requests.get", return_value=Mock(status_code=404, json=lambda: {"detail": "Unknown alarm"})):
            invalid_exp = explain_alarm("invalid")
            assert "unknown" in invalid_exp.lower()

    @pytest.mark.usefixtures("mock_openai", "mock_pinecone")
    def test_retrieve_guidance_tool_integration(self):
        """Test retrieve_guidance: queries Pinecone for claim advice."""
        query = "What documents are required for vehicle insurance claims?"

        mock_guidance = {
            "query": query,
            "response": "Please submit ID proof, RC book, and FIR copy.",
            "required_docs": ["ID proof", "RC book", "FIR copy"]
        }

        with patch(
            "chatbot.tools.retrieve_guidance.get_guidance_from_pinecone_or_db",
            return_value=(mock_guidance, 0.93)
        ):
            guidance = retrieve_guidance(query)

        # ✅ Validate output structure
        assert isinstance(guidance, dict)
        assert "response" in guidance
        assert isinstance(guidance["required_docs"], list)
        assert "ID" in guidance["required_docs"][0]
