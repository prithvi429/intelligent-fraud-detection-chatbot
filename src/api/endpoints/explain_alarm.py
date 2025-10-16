"""
Explain Alarm Endpoint
-----------------------
Provides human-friendly explanations for fraud alarms.
Used by chatbot, API clients, and UI dashboards.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import ORJSONResponse
from src.models.fraud import AlarmSeverity
from src.utils.logger import logger
from src.config import config

# =========================================================
# 🚀 Router Initialization
# =========================================================
router = APIRouter(tags=["Fraud Explanations"])

# =========================================================
# 🧠 Central Alarm Explanations
# =========================================================
ALARM_EXPLANATIONS = {
    "late_reporting": {
        "description": "This claim was reported long after the incident date, which may indicate false or delayed claims.",
        "severity": AlarmSeverity.MEDIUM,
        "tips": ["Provide dated evidence (police reports, photos, etc.)."],
    },
    "new_bank_account": {
        "description": "The payout bank account is newly added or unverified, which can trigger verification checks.",
        "severity": AlarmSeverity.MEDIUM,
        "tips": ["Upload a recent bank statement or verified ID proof."],
    },
    "high_amount": {
        "description": f"Claim amount exceeds the policy limit (${getattr(config, 'HIGH_AMOUNT_THRESHOLD', 10000)}). Large claims need extra verification.",
        "severity": AlarmSeverity.HIGH,
        "tips": ["Attach itemized invoices or detailed medical bills."],
    },
    "duplicate_claim": {
        "description": "This claim seems similar to a previously filed one from the same claimant.",
        "severity": AlarmSeverity.HIGH,
        "tips": ["Provide clarification or reference the earlier claim ID."],
    },
    "out_of_network": {
        "description": "The provider is outside your approved network. Manual review may be required.",
        "severity": AlarmSeverity.LOW,
        "tips": ["Submit referral letters or explain emergency context."],
    },
    "blacklisted_vendor": {
        "description": "The associated vendor or hospital has prior records of fraudulent claims.",
        "severity": AlarmSeverity.HIGH,
        "tips": ["Consider alternative approved providers."],
    },
    "external_data_mismatch": {
        "description": "Claim details do not align with verified external data sources (e.g., weather, accident reports).",
        "severity": AlarmSeverity.HIGH,
        "tips": ["Provide supporting third-party verification documents."],
    },
    "rapid_resubmission": {
        "description": "Multiple claims filed in a short timeframe may indicate automated or false entries.",
        "severity": AlarmSeverity.MEDIUM,
        "tips": ["Add notes explaining the resubmission reason."],
    },
}

# =========================================================
# 🎯 Endpoint: Explain Alarm (Query Param)
# =========================================================
@router.get("/explain_alarm")
async def explain_alarm(alarm_type: str = Query(..., description="Fraud alarm type to explain.")):
    """
    Returns a plain-text explanation for the given fraud alarm type.

    Example:
        GET /api/v1/explain_alarm?alarm_type=duplicate_claim
    """
    logger.info(f"📘 Received explanation request for alarm: {alarm_type}")

    # Validate input
    if not alarm_type:
        raise HTTPException(status_code=400, detail="Missing alarm_type parameter.")

    alarm_key = alarm_type.strip().lower()

    # If not found → 404
    if alarm_key not in ALARM_EXPLANATIONS:
        logger.warning(f"⚠️ Unknown alarm type requested: {alarm_key}")
        raise HTTPException(status_code=404, detail=f"Unknown alarm type: {alarm_key}")

    explanation = ALARM_EXPLANATIONS[alarm_key]
    logger.info(f"✅ Returning explanation for alarm: {alarm_key}")

    return ORJSONResponse(
        status_code=200,
        content={
            "alarm_type": alarm_key,
            "description": explanation["description"],
            "severity": explanation["severity"],
            "tips": explanation["tips"],
        },
    )
