"""
/explain/{alarm_type} Endpoint
------------------------------
Provides human-friendly explanations for fraud alarms.
Used by chatbot or frontend UI to guide users on resolving issues.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from src.models.fraud import FraudAlarm, AlarmSeverity
from src.api.dependencies import authenticated_user
from src.config import config
from src.utils.logger import logger

router = APIRouter(tags=["Fraud Explanations"])

# =========================================================
# 📘 Centralized alarm explanations (extendable to DB/Pinecone)
# =========================================================
ALARM_EXPLANATIONS = {
    "late_reporting": {
        "description": "This claim was reported more than 7 days after the incident. Late reports can sometimes indicate made-up or delayed claims.",
        "severity": AlarmSeverity.MEDIUM,
        "tips": ["Provide a police report or dated evidence of the incident."]
    },
    "new_bank_account": {
        "description": "The payout bank account is new or unverified. This could indicate identity issues.",
        "severity": AlarmSeverity.MEDIUM,
        "tips": ["Upload a recent bank statement or ID matching this account."]
    },
    "out_of_network_provider": {
        "description": "The provider is not in your approved network, which may trigger a manual review.",
        "severity": AlarmSeverity.LOW,
        "tips": ["Attach referral letters or explain emergency circumstances."]
    },
    "blacklist_hit": {
        "description": "The provider is on our fraud blacklist due to past overbilling or false claims.",
        "severity": AlarmSeverity.HIGH,
        "tips": ["Contact support for alternative verified providers."]
    },
    "suspicious_text_phrases": {
        "description": "Notes include words that match fraud-related phrases such as 'quick cash' or 'staged accident'.",
        "severity": AlarmSeverity.MEDIUM,
        "tips": ["Use factual language and include receipts or witness details."]
    },
    "high_amount": {
        "description": f"The claim amount exceeds the policy threshold (${config.HIGH_AMOUNT_THRESHOLD}). Large claims need supporting documentation.",
        "severity": AlarmSeverity.HIGH,
        "tips": ["Attach receipts, photos, or invoices for verification."]
    },
    "repeat_claimant": {
        "description": f"The claimant has filed more than {config.REPEAT_CLAIM_THRESHOLD} claims recently. Frequent filings may raise a review.",
        "severity": AlarmSeverity.MEDIUM,
        "tips": ["Include explanations or medical history for repeat cases."]
    },
    "suspicious_keywords": {
        "description": "Specific keywords in claim notes suggest exaggeration or inconsistencies.",
        "severity": AlarmSeverity.MEDIUM,
        "tips": ["Review and clarify your description using objective terms."]
    },
    "location_mismatch": {
        "description": f"The incident location is more than {config.LOCATION_DISTANCE_THRESHOLD} miles from your address, suggesting a possible mismatch.",
        "severity": AlarmSeverity.HIGH,
        "tips": ["Submit travel receipts or photos proving your presence there."]
    },
    "duplicate_claims": {
        "description": f"The claim text is {config.SIMILARITY_THRESHOLD * 100:.0f}% similar to a previous one, which may indicate resubmission.",
        "severity": AlarmSeverity.HIGH,
        "tips": ["Reference the prior claim ID if this is a follow-up."]
    },
    "vendor_fraud": {
        "description": "This vendor has a high-risk score due to previous suspicious activity.",
        "severity": AlarmSeverity.HIGH,
        "tips": ["Provide the vendor’s certification or use an in-network provider."]
    },
    "time_pattern_fraud": {
        "description": "The claim filing time (e.g., 3 AM or during weekends) is unusual for normal processing.",
        "severity": AlarmSeverity.MEDIUM,
        "tips": ["Add a note explaining why it was filed at this time."]
    },
    "external_data_mismatch": {
        "description": "Claim details do not match verified external data (e.g., no reported storm on date of accident).",
        "severity": AlarmSeverity.HIGH,
        "tips": ["Attach credible evidence such as weather or police reports."]
    },
}


# =========================================================
# 🎯 Endpoint: Explain Fraud Alarm
# =========================================================
@router.get(
    "/explain/{alarm_type}",
    response_model=FraudAlarm,
    summary="Explain a specific fraud alarm",
    description="Returns a human-readable explanation and tips for a given alarm type.",
)
async def explain_alarm_endpoint(
    alarm_type: str,
    user: dict = Depends(authenticated_user),
):
    """
    Get an explanation for a specific fraud alarm.
    Chatbot uses this to answer 'Why was my claim flagged?'
    """
    if not alarm_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Alarm type is required")

    alarm_key = alarm_type.lower().replace(" ", "_")

    if alarm_key not in ALARM_EXPLANATIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown alarm type: {alarm_type}. Valid types: {list(ALARM_EXPLANATIONS.keys())}",
        )

    expl = ALARM_EXPLANATIONS[alarm_key]
    tips_text = "; ".join(expl["tips"])
    full_description = f"{expl['description']} Suggested next steps: {tips_text}."

    logger.info(f"💬 Explained alarm '{alarm_type}' for user {user.get('user_id', 'anonymous')}")

    return FraudAlarm(
        type=alarm_key,
        description=full_description,
        severity=expl["severity"],
        evidence={"tips": expl["tips"], "source": "internal_guidelines_v1"},
    )
