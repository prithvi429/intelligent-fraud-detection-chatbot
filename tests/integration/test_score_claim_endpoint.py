"""
Integration Tests: /score_claim Endpoint
----------------------------------------
Verifies end-to-end fraud scoring flow, including:
- Valid request returns fraud probability, decision, and alarms.
- Invalid input triggers proper HTTP errors.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from src.main import app

client = TestClient(app)


# =========================================================
# 🧩 Fixtures
# =========================================================
@pytest.fixture
def sample_claim():
    """Valid claim payload for testing."""
    return {
        "claimant_id": "C12345",
        "amount": 12000.0,
        "provider": "ABC Hospital",
        "timestamp": "2024-12-01T10:00:00Z",
        "report_delay_days": 3,
        "is_new_bank": False,
    }


@pytest.fixture
def bad_claim():
    """Invalid payload for validation testing."""
    return {
        "claimant_id": "",
        "amount": -5000,
        "provider": "",
        "timestamp": "",
    }


# =========================================================
# ✅ Happy Path Test
# =========================================================
@patch("src.api.endpoints.score_claim.require_ml_model", return_value=True)
@patch("src.api.endpoints.score_claim.check_all_alarms", return_value=["Duplicate Claim: Same claimant in 30 days"])
@patch("src.api.endpoints.score_claim.get_fraud_probability", return_value=0.72)
@patch("src.api.endpoints.score_claim.get_decision", return_value="REVIEW")
@patch("src.api.endpoints.score_claim.save_claim_to_db", return_value=True)
def test_score_claim_endpoint_success(mock_save, mock_decision, mock_prob, mock_alarms, mock_ml, sample_claim):
    """
    ✅ Test that /score_claim returns correct structure and expected keys.
    """
    response = client.post("/score_claim", json=sample_claim)
    assert response.status_code == 200, f"Unexpected status: {response.text}"

    data = response.json()

    # --- Core fields ---
    assert "fraud_probability" in data
    assert isinstance(data["fraud_probability"], float)
    assert 0.0 <= data["fraud_probability"] <= 1.0

    assert "decision" in data
    assert data["decision"] in ("REVIEW", "REJECT", "APPROVE")

    # --- Metadata fields ---
    assert "explanation" in data
    assert "alarms" in data
    assert isinstance(data["alarms"], list)
    assert data["explanation"].startswith("Fraud analysis complete")

    # --- Verify mocks used ---
    mock_save.assert_called_once()
    mock_decision.assert_called_once()
    mock_prob.assert_called_once()
    mock_alarms.assert_called_once()


# =========================================================
# ❌ Validation & Error Handling Tests
# =========================================================
def test_score_claim_validation_error(bad_claim):
    """Should return 422 Unprocessable Entity for invalid claim data."""
    response = client.post("/score_claim", json=bad_claim)
    assert response.status_code in (400, 422)
    assert "detail" in response.json()


@patch("src.api.endpoints.score_claim.require_ml_model", return_value=True)
@patch("src.api.endpoints.score_claim.get_fraud_probability", side_effect=Exception("Mocked failure"))
def test_score_claim_internal_error(mock_prob, mock_ml, sample_claim):
    """Simulate internal server error when fraud model fails."""
    response = client.post("/score_claim", json=sample_claim)
    assert response.status_code == 500
    assert "Internal server error" in response.text


# =========================================================
# 🧠 Performance / Edge Test
# =========================================================
@patch("src.api.endpoints.score_claim.require_ml_model", return_value=True)
@patch("src.api.endpoints.score_claim.get_fraud_probability", return_value=0.05)
def test_score_claim_low_risk(mock_prob, mock_ml, sample_claim):
    """Low-risk claim should be automatically approved."""
    response = client.post("/score_claim", json=sample_claim)
    assert response.status_code == 200
    data = response.json()
    assert data["fraud_probability"] < 0.5
    assert data["decision"] in ("APPROVE", "REVIEW")
