"""
API Integration & Formatter Tests
---------------------------------
Tests:
  • utils/api_client.py — backend API interactions
  • utils/formatter.py — output formatting for Streamlit display

Covers:
  - 200, 4xx, timeout handling
  - Fraud, guidance, and alarm formatting
Run:
    pytest tests/test_api_integration.py -v
"""

import pytest
import responses
import requests
from unittest.mock import patch
from frontend.utils.api_client import call_score_claim, call_guidance, call_explain_alarm
from frontend.utils.formatter import (
    format_fraud_response,
    format_guidance_response,
    format_explain_alarm,
)

# --------------------------------------------------------------------
# 🧩 Sample backend responses
# --------------------------------------------------------------------
SAMPLE_FRAUD_RESPONSE = {
    "fraud_probability": 75.0,
    "decision": "Reject",
    "alarms": [{"type": "high_amount", "description": "Exceeds $10k", "severity": "high"}],
    "explanation": "Multiple red flags detected.",
}

SAMPLE_GUIDANCE_RESPONSE = {
    "guidance": {
        "response": "Submit ID and invoice.",
        "required_docs": ["ID", "Invoice"],
    },
    "relevance_score": 0.85,
}

SAMPLE_EXPLAIN_RESPONSE = {
    "type": "high_amount",
    "description": "Claim amount over threshold triggers review.",
    "severity": "high",
}


# --------------------------------------------------------------------
# 🌐 API CLIENT TESTS
# --------------------------------------------------------------------
class TestAPIClient:
    """Unit tests for frontend.utils.api_client.py"""

    @responses.activate
    def test_call_score_claim_success(self):
        """✅ Should return JSON when API responds 200."""
        responses.add(
            responses.POST,
            "http://localhost:8000/api/v1/score_claim",
            json=SAMPLE_FRAUD_RESPONSE,
            status=200,
        )

        claim_data = {"amount": 15000, "notes": "Test claim"}
        result = call_score_claim(claim_data)

        assert result == SAMPLE_FRAUD_RESPONSE
        assert len(responses.calls) == 1
        assert responses.calls[0].request.method == "POST"

    @responses.activate
    def test_call_score_claim_error_422(self):
        """❌ Validation error (422) → Returns None."""
        responses.add(
            responses.POST,
            "http://localhost:8000/api/v1/score_claim",
            json={"detail": "Invalid amount"},
            status=422,
        )
        result = call_score_claim({"amount": -100})
        assert result is None

    @responses.activate
    def test_call_score_claim_timeout(self):
        """⏱️ Timeout → Returns None."""
        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            result = call_score_claim({"amount": 5000})
        assert result is None

    @responses.activate
    def test_call_guidance_success(self):
        """✅ Should return JSON when guidance API succeeds."""
        responses.add(
            responses.POST,
            "http://localhost:8000/api/v1/guidance",
            json=SAMPLE_GUIDANCE_RESPONSE,
            status=200,
        )
        result = call_guidance("What docs?")
        assert result == SAMPLE_GUIDANCE_RESPONSE

    @responses.activate
    def test_call_explain_alarm_success(self):
        """✅ Explain alarm (200) returns parsed dict."""
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/explain/high_amount",
            json=SAMPLE_EXPLAIN_RESPONSE,
            status=200,
        )
        result = call_explain_alarm("high_amount")
        assert result == SAMPLE_EXPLAIN_RESPONSE

    @responses.activate
    def test_call_explain_alarm_404(self):
        """❌ 404 error → Returns None."""
        responses.add(
            responses.GET,
            "http://localhost:8000/api/v1/explain/invalid",
            json={"detail": "Not found"},
            status=404,
        )
        result = call_explain_alarm("invalid")
        assert result is None


# --------------------------------------------------------------------
# 🎨 FORMATTER TESTS
# --------------------------------------------------------------------
class TestFormatter:
    """Unit tests for frontend.utils.formatter.py"""

    def test_format_fraud_response_full(self):
        """✅ Full fraud response formatted properly."""
        formatted = format_fraud_response(SAMPLE_FRAUD_RESPONSE)

        assert "decision-reject" in formatted["decision_class"]
        assert "75.0%" in formatted["text"]
        assert "- **High Amount**" in formatted["text"]
        assert len(formatted["formatted_alarms"]) == 1
        assert formatted["formatted_alarms"][0]["icon"] == "🚨"

    def test_format_fraud_response_no_alarms(self):
        """No alarms → shows success note."""
        no_alarm_resp = {**SAMPLE_FRAUD_RESPONSE, "alarms": []}
        formatted = format_fraud_response(no_alarm_resp)
        assert "No fraud alarms triggered" in formatted["text"] or "✅" in formatted["text"]
        assert len(formatted["formatted_alarms"]) == 0

    def test_format_fraud_response_empty(self):
        """Empty dict → uses defaults."""
        formatted = format_fraud_response({})
        assert "Decision" in formatted["text"]
        assert "0.0%" in formatted["text"]

    def test_format_guidance_response_full(self):
        """✅ Guidance response: Contains docs + score."""
        formatted = format_guidance_response(SAMPLE_GUIDANCE_RESPONSE)
        assert "Submit ID and invoice." in formatted
        assert "Required Documents" in formatted
        assert "85.0%" in formatted

    def test_format_guidance_response_no_docs(self):
        """Guidance with no docs → skips document section."""
        no_docs = {**SAMPLE_GUIDANCE_RESPONSE, "guidance": {"response": "Only ID", "required_docs": []}}
        formatted = format_guidance_response(no_docs)
        assert "Required Documents" not in formatted

    def test_format_explain_alarm_high(self):
        """High severity → 🚨 emoji present."""
        formatted = format_explain_alarm(SAMPLE_EXPLAIN_RESPONSE)
        assert "🚨" in formatted
        assert "High Amount" in formatted

    def test_format_explain_alarm_low(self):
        """Low severity → ℹ️ emoji."""
        low_resp = {**SAMPLE_EXPLAIN_RESPONSE, "severity": "low"}
        formatted = format_explain_alarm(low_resp)
        assert "ℹ️" in formatted
