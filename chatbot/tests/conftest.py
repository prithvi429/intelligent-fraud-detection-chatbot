"""
Shared Fixtures for Chatbot Tests
---------------------------------
Centralized pytest fixtures for mocking:
- Settings (env & constants)
- Backend API responses
- Pinecone client
- LLM (OpenAI)
- SessionManager
"""

import pytest
from unittest.mock import MagicMock, patch
import responses
from chatbot.config import settings


# ===============================
# 🧩 SETTINGS FIXTURE
# ===============================
@pytest.fixture
def mock_settings():
    """Mock environment-level settings (API keys, URLs, thresholds)."""
    with patch("chatbot.config.settings.settings") as mock:
        mock.OPENAI_API_KEY = "fake_key"
        mock.BACKEND_URL = "http://test-backend.com"
        mock.PINECONE_ENABLED = True
        mock.PINECONE_API_KEY = "fake_pinecone"
        mock.PINECONE_INDEX_NAME = "test-index"
        mock.MAX_TOKENS = 4000
        yield mock


# ===============================
# 🌐 API MOCK RESPONSES
# ===============================
@pytest.fixture
def mock_api_responses():
    """Intercept external API calls from tools → returns fake JSON responses."""
    with responses.RequestsMock() as rsps:
        # Mock /score_claim
        rsps.add(
            responses.POST,
            "http://test-backend.com/api/v1/score_claim",
            json={
                "fraud_probability": 75.0,
                "decision": "Reject",
                "alarms": [
                    {
                        "type": "high_amount",
                        "description": "Exceeds threshold",
                        "severity": "high"
                    }
                ],
                "explanation": "High risk detected."
            },
            status=200,
        )

        # Mock /explain/{type}
        rsps.add(
            responses.GET,
            "http://test-backend.com/api/v1/explain/high_amount",
            json={
                "type": "high_amount",
                "description": "Amount over $10k",
                "severity": "high",
                "mitigation": "Provide proof"
            },
            status=200,
        )

        # Mock /guidance
        rsps.add(
            responses.POST,
            "http://test-backend.com/api/v1/guidance",
            json={
                "guidance": {
                    "response": "Submit ID.",
                    "required_docs": ["ID"]
                },
                "relevance_score": 0.85
            },
            status=200,
        )

        # Mock error endpoint
        rsps.add(
            responses.POST,
            "http://test-backend.com/api/v1/score_claim_error",
            json={"detail": "Invalid"},
            status=422,
        )
        yield rsps


# ===============================
# 🔍 PINECONE MOCK
# ===============================
@pytest.fixture
def mock_pinecone():
    """Fake Pinecone client and search results."""
    with patch("pinecone.init") as mock_init, patch("pinecone.Index") as mock_index:
        mock_init.return_value = MagicMock()
        mock_index_instance = MagicMock()

        mock_match = MagicMock()
        mock_match.score = 0.95
        mock_match.metadata = {
            "response": "Test guidance",
            "required_docs": ["ID"],
            "source": "Policy"
        }

        mock_index_instance.query.return_value.matches = [mock_match]
        mock_index.return_value = mock_index_instance
        yield mock_index_instance


# ===============================
# 🧠 LLM MOCK
# ===============================
@pytest.fixture
def mock_llm():
    """Mock LangChain ChatOpenAI model for agent tests."""
    with patch("langchain_openai.ChatOpenAI") as mock_chat:
        mock_instance = MagicMock()
        mock_chat.return_value = mock_instance
        yield mock_instance


# ===============================
# 💬 SESSION MANAGER MOCK
# ===============================
@pytest.fixture
def mock_session():
    """Mock SessionManager (conversation history)."""
    with patch("chatbot.utils.session_manager.SessionManager") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.add_message.return_value = None
        mock_instance.get_history.return_value = []
        mock_cls.return_value = mock_instance
        yield mock_instance
