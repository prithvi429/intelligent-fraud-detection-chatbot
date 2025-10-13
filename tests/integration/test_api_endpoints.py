"""
Integration Tests: API Endpoints
--------------------------------
Validates full behavior of API routes using TestClient.

Includes:
- Fraud scoring endpoint (/api/v1/score_claim)
- Alarm explanations (/api/v1/explain/{type})
- Policy guidance (/api/v1/guidance)
- Health and root endpoints
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from src.main import app
from src.models.fraud import Decision

# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    """Return FastAPI test client with middleware loaded."""
    return TestClient(app)


# ---------------------------------------------------------------------
# /api/v1/score_claim
# ---------------------------------------------------------------------
@patch("src.utils.logger.logger.info")
@patch("src.utils.logger.logger.error")
def test_score_claim_high_risk(mock_error, mock_info, client):
    """POST high-risk claim → REJECT decision + logs emitted."""
    payload = {
        "amount": 15000.0,
        "report_delay_days": 10,
        "provider": "shady_clinic",
        "notes": "Staged accident quick cash",
        "claimant_id": "api_test_user",
        "location": "Los Angeles, CA",
        "is_new_bank": True
    }

    response = client.post("/api/v1/score_claim", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "fraud_probability" in data
    assert 0 <= data["fraud_probability"] <= 100
    assert data["decision"] == Decision.REJECT.value
    assert any("risk" in data["explanation"].lower() or "reject" in data["explanation"].lower() for _ in [0])
    assert len(data["alarms"]) >= 3

    # Logging checks
    assert mock_info.call_count >= 2
    assert '"event": "request_start"' in mock_info.call_args_list[0][0][0]
    assert '"event": "request_end"' in mock_info.call_args_list[-1][0][0]
    mock_error.assert_not_called()


@patch("src.utils.logger.logger.info")
def test_score_claim_low_risk(mock_info, client):
    """POST low-risk claim → APPROVE decision."""
    payload = {
        "amount": 1000.0,
        "report_delay_days": 1,
        "provider": "trusted_clinic",
        "notes": "Normal claim",
        "claimant_id": "lowrisk_api_user",
        "location": "NYC",
        "is_new_bank": False
    }

    response = client.post("/api/v1/score_claim", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["decision"] == Decision.APPROVE.value
    assert data["fraud_probability"] < 30
    assert len(data["alarms"]) == 0
    assert "low risk" in data["explanation"].lower()

    # Ensure logs emitted
    assert any('"request_start"' in call[0][0] for call in mock_info.call_args_list)


@patch("src.utils.logger.logger.error")
def test_score_claim_validation_error(mock_error, client):
    """POST invalid claim → 422 validation error + error log."""
    payload = {
        "amount": -500.0,
        "report_delay_days": 2,
        "provider": "ABC",
        "notes": "Invalid claim",
        "claimant_id": "invalid_user",
        "location": "NY"
    }

    response = client.post("/api/v1/score_claim", json=payload)
    assert response.status_code == 422
    assert "invalid input" in str(response.json()).lower()

    # Error log check
    mock_error.assert_called_once()
    log_data = mock_error.call_args[0][0]
    assert '"event": "request_error"' in log_data
    assert any(x in log_data for x in ["ValidationError", "422"])


# ---------------------------------------------------------------------
# /api/v1/explain/{type}
# ---------------------------------------------------------------------
def test_explain_alarm_valid_and_invalid(client):
    """GET explanation for valid & invalid alarm."""
    valid = client.get("/api/v1/explain/high_amount")
    assert valid.status_code == 200
    assert "high_amount" in valid.json()["type"]

    invalid = client.get("/api/v1/explain/unknown_alarm")
    assert invalid.status_code == 404
    assert "unknown" in invalid.json()["detail"].lower()


# ---------------------------------------------------------------------
# /api/v1/guidance
# ---------------------------------------------------------------------
def test_get_guidance_valid_and_empty(client):
    """POST valid and empty guidance queries."""
    valid = client.post("/api/v1/guidance", json={"query": "What documents are required?"})
    assert valid.status_code == 200
    data = valid.json()

    assert "guidance" in data
    assert "document" in data["guidance"]["response"].lower()
    assert data["relevance_score"] >= 0.5

    # Empty query
    empty = client.post("/api/v1/guidance", json={"query": ""})
    assert empty.status_code == 400


# ---------------------------------------------------------------------
# Health and Root Endpoints
# ---------------------------------------------------------------------
def test_health_endpoint(client):
    """GET /health returns system status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "degraded"]


def test_root_endpoint_metadata(client):
    """GET / returns metadata and system info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "status" in data
    assert "timestamp" in data
