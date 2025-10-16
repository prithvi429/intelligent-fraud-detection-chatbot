"""
Unit Tests: Decision Policy
---------------------------
Covers src/fraud_engine/decision_policy.py (get_decision & get_simple_decision).
Validates:
- Decision boundaries: Low / Medium / High risk
- Severity weights effect
- Edge cases (no alarms, no claim)
- Log output

Run:
    pytest tests/unit/test_decision_policy.py -v
"""

import pytest
from src.models.claim import ClaimData
from src.models.fraud import Decision, FraudAlarm, AlarmSeverity
from src.fraud_engine.decision_policy import get_decision, get_simple_decision


class TestDecisionPolicy:
    """Unit tests for decision_policy.py."""

    # --------------------------------------
    # ✅ Low / Medium / High Risk Decisions
    # --------------------------------------
    def test_get_decision_low_risk(self):
        """Low prob + no alarms → APPROVE."""
        alarms = []
        decision = get_decision(20.0, alarms)
        assert decision == Decision.APPROVE

        simple_decision = get_simple_decision(20.0, 0)
        assert simple_decision == Decision.APPROVE

    def test_get_decision_medium_risk(self):
        """Medium prob + 2 low/medium alarms → REVIEW."""
        alarms = [
            FraudAlarm(type="late_reporting", description="Late reporting of claim", severity=AlarmSeverity.LOW),
            FraudAlarm(type="out_of_network", description="Out of network provider", severity=AlarmSeverity.MEDIUM),
        ]
        decision = get_decision(50.0, alarms)
        assert decision == Decision.REVIEW

        simple_decision = get_simple_decision(50.0, len(alarms))
        assert simple_decision == Decision.REVIEW

    def test_get_decision_high_risk(self):
        """High prob + 3 high-severity alarms → REJECT."""
        alarms = [
            FraudAlarm(type="high_amount", description="High claim amount", severity=AlarmSeverity.HIGH),
            FraudAlarm(type="blacklist_hit", description="Blacklisted provider", severity=AlarmSeverity.HIGH),
            FraudAlarm(type="duplicate_claims", description="Duplicate claims found", severity=AlarmSeverity.HIGH),
        ]
        decision = get_decision(80.0, alarms)
        assert decision == Decision.REJECT

        simple_decision = get_simple_decision(80.0, len(alarms))
        assert simple_decision == Decision.REJECT

    # --------------------------------------
    # ✅ Severity Weight Tests
    # --------------------------------------
    def test_high_severity_weights_increase_risk(self):
        """High-severity alarms push total_risk into REJECT."""
        # Medium probability but multiple high-severity alarms
        high_sev_alarms = [
            FraudAlarm(type="vendor_fraud", description="Vendor fraud detected", severity=AlarmSeverity.HIGH),
            FraudAlarm(type="location_mismatch", description="Location data mismatch", severity=AlarmSeverity.HIGH),
        ]
        decision_high = get_decision(60.0, high_sev_alarms)
        assert decision_high == Decision.REJECT

        # Same scenario, but with low severity → REVIEW
        low_sev_alarms = [
            FraudAlarm(type="vendor_fraud", description="Vendor fraud detected", severity=AlarmSeverity.LOW),
            FraudAlarm(type="location_mismatch", description="Location data mismatch", severity=AlarmSeverity.LOW),
        ]
        decision_low = get_decision(60.0, low_sev_alarms)
        assert decision_low == Decision.REVIEW

    # --------------------------------------
    # ✅ Edge Cases
    # --------------------------------------
    def test_edge_cases(self):
        """Edge: high prob/no alarms → REJECT; low prob/many alarms → REVIEW."""
        # Case 1: High probability dominates
        dec_high_prob = get_decision(85.0, [])
        assert dec_high_prob == Decision.REJECT

        # Case 2: Low probability, but multiple low alarms (still not REJECT)
        alarms_many_low = [
            FraudAlarm(type=f"alarm{i}", description=f"Low alarm {i}", severity=AlarmSeverity.LOW)
            for i in range(5)
        ]
        dec_many_low = get_decision(20.0, alarms_many_low)
        assert dec_many_low == Decision.REVIEW

        # Case 3: No claim (for log safety)
        dec_no_claim = get_decision(
            50.0,
            [FraudAlarm(type="test", description="test alarm", severity=AlarmSeverity.MEDIUM)],
            claim=None
        )
        assert dec_no_claim == Decision.REVIEW

    # --------------------------------------
    # ✅ Consistency Between Simple and Weighted
    # --------------------------------------
    def test_simple_vs_weighted_consistency(self):
        """Simple decision and weighted decision align in basic scenarios."""
        alarms = [FraudAlarm(type="test_alarm", description="Medium alarm", severity=AlarmSeverity.MEDIUM)]
        weighted = get_decision(40.0, alarms)
        simple = get_simple_decision(40.0, len(alarms))
        assert weighted == simple  # Both REVIEW

    # --------------------------------------
    # ✅ Logging Behavior
    # --------------------------------------
    def test_logging_output(self, caplog):
        """Ensure logging includes claim details and decision outcome."""
        alarms = [FraudAlarm(type="high_alarm", description="High severity", severity=AlarmSeverity.HIGH)]
        with caplog.at_level("INFO"):
            # ✅ Provide minimal valid fields for ClaimData
            get_decision(
                75.0,
                alarms,
                claim=ClaimData(amount=1000, provider="TestProvider", claimant_id="log_test_user")
            )
        log_text = caplog.text.lower()
        assert "decision" in log_text
        assert "log_test_user" in log_text
        assert "reject" in log_text or "review" in log_text
