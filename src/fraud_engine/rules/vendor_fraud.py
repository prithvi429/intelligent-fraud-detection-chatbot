"""
Vendor Fraud Check
------------------
Identifies potential fraudulent providers using:
1️⃣ Internal blacklist (DB lookup)
2️⃣ External vendor risk API (fallback to internal if unavailable)

Triggers alarm if:
- Vendor appears in blacklist
- External API risk_score > configured threshold (default: 0.7)

Example:
["[VENDOR-FRAUD] Provider 'shady_clinic' risk=0.85 – Blacklist hit or API flag"]
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
    Detects vendor-level fraud using internal blacklist and/or external API risk signals.

    Args:
        claim (ClaimData): Claim containing provider details.
        db (Session, optional): DB session for blacklist lookup (optional).

    Returns:
        List[str]: Fraud alarm messages if vendor is risky or blacklisted.
    """
    alarms: List[str] = []
    provider = (getattr(claim, "provider", "") or "").strip()
    claimant_id = getattr(claim, "claimant_id", "unknown")

    if not provider:
        logger.debug("[VENDOR-FRAUD] No provider specified — skipping check.")
        return alarms

    try:
        # Step 1️⃣ Check internal blacklist
        blacklisted = False
        try:
            blacklist = get_blacklist_providers(db) if db else []
            if any(provider.lower() in bl.lower() for bl in blacklist):
                alarms.append(
                    f"[VENDOR-FRAUD] Provider '{provider}' is blacklisted (internal DB check)."
                )
                blacklisted = True
                logger.info(f"[VENDOR-FRAUD] 🚨 Blacklist hit for provider '{provider}'.")
        except Exception as e:
            logger.warning(f"[VENDOR-FRAUD] ⚠️ Blacklist check failed for '{provider}': {e}")

        # Step 2️⃣ External API risk check (optional)
        vendor_result = {}
        try:
            vendor_result = check_vendor_risk(provider, db)
        except Exception as e:
            logger.warning(f"[VENDOR-FRAUD] ⚠️ External vendor API unavailable for '{provider}': {e}")

        risk_score = float(vendor_result.get("risk_score", 0.0)) if vendor_result else 0.0
        reason = vendor_result.get("reason", "No risk reason returned") if vendor_result else "N/A"
        threshold = getattr(config, "ML_FRAUD_THRESHOLD", 0.7)

        # Step 3️⃣ Evaluate combined results
        if blacklisted or risk_score > threshold:
            alarms.append(
                f"[VENDOR-FRAUD] Provider '{provider}' risk={risk_score:.2f} "
                f"– {reason}{' (blacklist hit)' if blacklisted else ''}."
            )
            logger.info(
                f"[VENDOR-FRAUD] 🚨 Vendor flagged: provider='{provider}', risk={risk_score:.2f}, reason={reason}"
            )
        else:
            logger.debug(f"[VENDOR-FRAUD] OK – Provider '{provider}' risk={risk_score:.2f}, threshold={threshold:.2f}")

    except Exception as e:
        logger.error(f"[VENDOR-FRAUD] ❌ Unexpected error for provider '{provider}' (claimant={claimant_id}): {e}")

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
        notes="Routine verification claim",
    )

    print("\n🚨 Vendor Fraud Alarms:")
    for alarm in check_vendor_fraud(claim):
        print("•", alarm)
