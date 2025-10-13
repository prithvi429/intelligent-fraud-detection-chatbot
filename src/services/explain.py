"""
Explanation Service
-------------------
Provides human-readable explanations for fraud alarms.

This service acts as the data layer for /api/v1/explain/{alarm_name}.
It can later be replaced or extended with database queries, vector
similarity search (Pinecone, FAISS), or an AI-driven knowledge base.

For now, it returns static, well-defined explanations used in tests.
"""

from typing import Optional
from src.utils.logger import logger


def get_explanation_for_alarm(alarm_name: str) -> Optional[dict]:
    """
    Retrieve a structured explanation for a given fraud alarm name.

    Args:
        alarm_name (str): Name or key of the fraud alarm.

    Returns:
        dict | None: Explanation dict with `type` and `description`
                     if found, otherwise None.
    """

    logger.info(f"🔍 Looking up explanation for alarm: {alarm_name}")

    explanations = {
        "high_amount": {
            "type": "high_amount",
            "description": (
                "High claim amount often correlates with potential fraud risk "
                "due to unusually large or inflated claim values."
            ),
        },
        "shady_provider": {
            "type": "shady_provider",
            "description": (
                "The provider has a history of suspicious or fraudulent activity "
                "and is flagged for manual review."
            ),
        },
        "delayed_report": {
            "type": "delayed_report",
            "description": (
                "This claim was reported significantly after the incident date. "
                "Late reporting can sometimes indicate delayed or manipulated claims."
            ),
        },
        "new_bank": {
            "type": "new_bank",
            "description": (
                "The payout bank account is recently created or unverified. "
                "New accounts may require additional validation to prevent identity misuse."
            ),
        },
        "repeat_claimant": {
            "type": "repeat_claimant",
            "description": (
                "This claimant has filed multiple claims within a short period. "
                "Frequent submissions may indicate claim pattern anomalies."
            ),
        },
        "suspicious_keywords": {
            "type": "suspicious_keywords",
            "description": (
                "Claim notes include suspicious or exaggerated keywords "
                "that match known fraud indicators."
            ),
        },
        "location_mismatch": {
            "type": "location_mismatch",
            "description": (
                "The claim’s reported location doesn’t match the claimant’s usual address. "
                "Possible case of fabricated or incorrect incident details."
            ),
        },
    }

    alarm_key = str(alarm_name).strip().lower()

    # ✅ Return the explanation if found
    if alarm_key in explanations:
        logger.info(f"✅ Found explanation for alarm: {alarm_key}")
        return explanations[alarm_key]

    # ❌ Return None if alarm not found
    logger.warning(f"⚠️ No explanation found for alarm: {alarm_key}")
    return None
