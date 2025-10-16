"""
Decision Policy Engine
----------------------
Combines ML probability and fraud alarms to produce a business decision.

Decisions:
- APPROVE: Low risk (few alarms, low probability)
- REVIEW: Medium risk (moderate alarms or ML uncertainty)
- REJECT: High risk (many or severe alarms)

Configurable via risk weights and thresholds.
"""

from typing import List, Optional, Dict, Any
from src.models.claim import ClaimData
from src.models.fraud import Decision, FraudAlarm, AlarmSeverity
from src.config import config
from src.utils.logger import logger

# Tunable thresholds (can be moved into config or DB)
THRESHOLD_APPROVE = 0.30   # <30% = approve
THRESHOLD_REVIEW = 0.70    # 30–70% = manual review
ALARM_WEIGHT = 0.10        # Each alarm adds 10%
HIGH_SEVERITY_WEIGHT = 0.20  # Each high-severity alarm adds 20%


def _compute_risk_score(prob: float, alarms: List[FraudAlarm]) -> float:
    """Combine model probability and alarms into unified risk score."""
    prob = min(prob, 100) / 100.0  # Normalize 0–1 range
    num_alarms = len(alarms)
    high_count = len([a for a in alarms if a.severity == AlarmSeverity.HIGH])
    alarm_weight = (num_alarms * ALARM_WEIGHT) + (high_count * HIGH_SEVERITY_WEIGHT)
    return round(prob + alarm_weight, 2)


def get_decision(
    fraud_prob: float,
    alarms: List[FraudAlarm],
    claim: Optional[ClaimData] = None,
    return_details: bool = False
) -> Decision | Dict[str, Any]:
    """
    Determine final fraud decision based on probability + alarms.

    Args:
        fraud_prob: ML model probability (0–100)
        alarms: List of FraudAlarm objects
        claim: Optional ClaimData (for context)
        return_details: If True, returns dict with reasoning info

    Returns:
        Decision enum or dict with details.
    """
    total_risk = _compute_risk_score(fraud_prob, alarms)
    num_alarms = len(alarms)
    high_count = len([a for a in alarms if a.severity == AlarmSeverity.HIGH])

    # ✅ Updated Decision Logic
    if fraud_prob >= 75 or high_count >= 2 or total_risk >= 1.2:
        decision = Decision.REJECT
        reason = "High risk: multiple or severe alarms + high fraud probability."
    elif fraud_prob >= 30 or num_alarms > 0:
        decision = Decision.REVIEW
        reason = "Medium risk: moderate alarms or uncertain ML confidence."
    else:
        decision = Decision.APPROVE
        reason = "Low risk: minimal alarms and low probability."

    # Structured log for traceability
    log_data = {
        "claimant_id": getattr(claim, "claimant_id", "unknown"),
        "decision": decision.value,
        "fraud_prob": f"{fraud_prob:.1f}%",
        "alarms": num_alarms,
        "high_severity": high_count,
        "total_risk": total_risk,
        "reason": reason
    }
    logger.info(f"[DECISION] {log_data}")

    # Return type flexibility
    if return_details:
        return {
            "decision": decision.value,
            "total_risk": total_risk,
            "fraud_prob": fraud_prob,
            "num_alarms": num_alarms,
            "high_severity": high_count,
            "reason": reason,
        }

    return decision


def get_simple_decision(fraud_prob: float, num_alarms: int) -> Decision:
    """Basic version for lightweight or unit testing scenarios."""
    if fraud_prob < 30 and num_alarms == 0:
        return Decision.APPROVE
    elif fraud_prob < 70 or num_alarms <= 2:
        return Decision.REVIEW
    return Decision.REJECT


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    from src.models.fraud import FraudAlarm, AlarmSeverity
    from src.models.claim import ClaimData

    claim = ClaimData(amount=8000, provider="ClinicX", claimant_id="demo_user")

    alarms = [
        FraudAlarm(type="high_amount", description="Claim exceeds threshold", severity=AlarmSeverity.HIGH),
        FraudAlarm(type="late_reporting", description="Filed after 10 days", severity=AlarmSeverity.MEDIUM),
    ]

    print("Low Risk →", get_decision(20.0, [], claim, return_details=True))
    print("Medium Risk →", get_decision(55.0, [alarms[1]], claim, return_details=True))
    print("High Risk →", get_decision(85.0, alarms, claim, return_details=True))
