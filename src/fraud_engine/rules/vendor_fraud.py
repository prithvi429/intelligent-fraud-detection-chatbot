"""
Vendor Fraud Check
------------------
Identifies potential fraudulent providers using:
1. Internal blacklist (local DB check)
2. External vendor risk API (fallback to internal if unavailable)

Triggers alarm if:
- Vendor is blacklisted
- External API risk_score > configured threshold (default: 0.7)

Example:
["Vendor fraud: Provider 'shady_clinic' risk score 0.85 – Internal blacklist hit"]
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from src.models.claim import ClaimData
from src.utils.external_apis import check_vendor_fraud as check_vendor_risk
from src.utils.db import get_blacklist_providers
from src.utils.logger import logger
from src.config import config


def check_vendor_fraud(claim: ClaimData, db: Optional[Session] = None) -> List[str]:
    """
    Detects vendor-level fraud using blacklist and/or external APIs.

    Args:
        claim (ClaimData): Claim containing provider info.
        db (Session, optional): DB session for blacklist fallback.

    Returns:
        List[str]: Fraud alarms.
    """
    alarms: List[str] = []
    provider = (claim.provider or "").strip()

    if not provider:
        logger.debug("[VENDOR-FRAUD] No provider specified — skipping check.")
        return alarms

    try:
        # Step 1: Run API/DB check
        vendor_result = check_vendor_risk(provider, db)
        if not vendor_result:
            logger.warning(f"[VENDOR-FRAUD] No result returned for provider '{provider}'.")
            return alarms

        is_fraud = vendor_result.get("is_fraudulent", False)
        risk_score = float(vendor_result.get("risk_score", 0.0))
        reason = vendor_result.get("reason", "Unknown reason")

        # Step 2: Evaluate thresholds
        threshold = config.ML_FRAUD_THRESHOLD
        if is_fraud or risk_score > threshold:
            alarms.append(
                f"Vendor fraud: Provider '{provider}' risk score {risk_score:.2f} – {reason}"
            )
            logger.info(f"[VENDOR-FRAUD] 🚨 Fraud alert: {provider} risk={risk_score:.2f} ({reason})")
        else:
            logger.debug(f"[VENDOR-FRAUD] OK – {provider} risk={risk_score:.2f}")

    except Exception as e:
        logger.error(f"[VENDOR-FRAUD] Error during vendor fraud check for '{provider}': {e}")

    return alarms


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    from src.models.claim import ClaimData

    claim = ClaimData(
        amount=5000,
        provider="shady_clinic",
        claimant_id="user_demo",
        notes="",
    )

    print("🚨 Alarms:", check_vendor_fraud(claim))


