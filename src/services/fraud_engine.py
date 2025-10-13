"""
Fraud Engine Service
--------------------
Handles fraud scoring, risk assessment, and decision logic.
This mock implementation aligns with test expectations.
"""

from src.models.fraud import Decision
from src.utils.logger import logger

async def score_claim(claim: dict):
    """Mock fraud scoring logic with rule-based and probability evaluation."""

    amount = claim.get("amount", 0)
    delay = claim.get("report_delay_days", 0)
    provider = (claim.get("provider") or "").lower()
    is_new_bank = claim.get("is_new_bank", False)

    fraud_probability = 0
    alarms = []

    # 🔹 Rule 1: High amount
    if amount > 10000:
        fraud_probability += 40
        alarms.append("high_amount")

    # 🔹 Rule 2: Shady provider
    if "shady" in provider:
        fraud_probability += 30
        alarms.append("shady_provider")

    # 🔹 Rule 3: Long report delay
    if delay > 7:
        fraud_probability += 20
        alarms.append("delayed_report")

    # 🔹 Rule 4: New bank account risk
    if is_new_bank:
        fraud_probability += 10
        alarms.append("new_bank")

    fraud_probability = min(fraud_probability, 100)

    # Decision thresholds
    if fraud_probability < 30:
        decision = Decision.APPROVE.value
        explanation = "Low risk — claim approved automatically."
    elif 30 <= fraud_probability <= 70:
        decision = Decision.REVIEW.value
        explanation = "Medium risk — requires manual review."
    else:
        decision = Decision.REJECT.value
        explanation = "High risk — claim rejected due to suspicious indicators."

    logger.info(
        f"🧠 Scored claim {claim.get('claimant_id')}: {decision} ({fraud_probability}%)"
    )

    return {
        "fraud_probability": fraud_probability,
        "decision": decision,
        "alarms": alarms,
        "explanation": explanation,
    }
