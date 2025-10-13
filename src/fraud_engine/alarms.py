"""
Fraud Alarms Orchestrator
-------------------------
Runs all 13 fraud detection checks on a claim.

- 5 legacy (rule-based): 
  late reporting, new bank, out-of-network, blacklist, suspicious text.
- 8 modular (modern ML+rule hybrid):
  high amount, repeat claimant, suspicious keywords, location mismatch,
  duplicate claims, vendor fraud, time patterns, external mismatch.

Usage:
    alarms = check_all_alarms(claim, db)
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from datetime import datetime

from src.models.claim import ClaimData
from src.utils.logger import logger
from src.utils.db import get_blacklist_providers
from src.nlp.text_analyzer import analyze_text
from src.fraud_engine.constants import SUSPICIOUS_PHRASES

# Modular rule imports (independent files)
from src.fraud_engine.rules.high_amount import check_high_amount
from src.fraud_engine.rules.repeat_claimant import check_repeat_claimant
from src.fraud_engine.rules.suspicious_keywords import check_suspicious_keywords
from src.fraud_engine.rules.location_mismatch import check_location_mismatch
from src.fraud_engine.rules.duplicate_claims import check_duplicate_claims
from src.fraud_engine.rules.vendor_fraud import check_vendor_fraud
from src.fraud_engine.rules.time_patterns import check_time_patterns
from src.fraud_engine.rules.external_mismatch import check_external_mismatch


def check_all_alarms(claim: ClaimData, db: Optional[Session] = None) -> List[str]:
    """
    Run all fraud detection checks sequentially.

    Args:
        claim (ClaimData): Claim to evaluate.
        db (Session, optional): SQLAlchemy session (for vendor/claim lookups).

    Returns:
        List[str]: List of detected fraud alarm messages.
    """
    alarms: List[str] = []
    provider = (claim.provider or "").lower()
    notes = (claim.notes or "").strip().lower()

    logger.info(
        f"🧠 Running fraud detection for claimant={claim.claimant_id}, amount=${claim.amount:.2f}"
    )

    # =====================================================
    # 🔹 LEGACY RULES (Base)
    # =====================================================

    # 1️⃣ Late Reporting
    delay_days = getattr(claim, "report_delay_days", 0)
    if delay_days > 7:
        alarms.append(
            f"[LATE-REPORT] Reported {delay_days} days after incident (limit: 7 days)"
        )

    # 2️⃣ New Bank Account
    if getattr(claim, "is_new_bank", False):
        alarms.append(
            "[NEW-BANK] Payout requested to a new or unverified bank account"
        )

    # 3️⃣ Out-of-Network Provider
    if "out-of-network" in provider or "non-network" in provider:
        alarms.append(
            f"[OUT-NETWORK] Provider '{claim.provider}' not in approved insurer network"
        )

    # 4️⃣ Blacklist Hit
    blacklist_providers = get_blacklist_providers(db) if db else ["shady_clinic", "fake_vendor"]
    for bl in blacklist_providers:
        if bl.lower() in provider:
            alarms.append(f"[BLACKLIST] Provider '{claim.provider}' flagged (blacklist match: {bl})")
            break

    # 5️⃣ Suspicious Text Phrases (NLP-based)
    if notes:
        try:
            nlp_results = analyze_text(notes)
            matched = [
                p for p in SUSPICIOUS_PHRASES if p in notes
            ] + nlp_results.get("suspicious_phrases", [])
            if matched:
                top_phrases = ", ".join(matched[:3])
                alarms.append(f"[TEXT-FLAG] Suspicious language detected: {top_phrases}")
        except Exception as e:
            logger.error(f"[TEXT-ANALYSIS] Failed NLP phrase check: {e}")

    # =====================================================
    # 🔹 MODULAR RULES (Modern)
    # =====================================================
    try:
        alarms += check_high_amount(claim, db)
        alarms += check_repeat_claimant(claim, db)
        alarms += check_suspicious_keywords(claim, db)
        alarms += check_location_mismatch(claim, db)
        alarms += check_duplicate_claims(claim, db)
        alarms += check_vendor_fraud(claim, db)
        alarms += check_time_patterns(claim, db)
        alarms += check_external_mismatch(claim, db)
    except Exception as e:
        logger.error(f"[ORCHESTRATOR] Error running modular checks: {e}")

    # =====================================================
    # ✅ Summary
    # =====================================================
    total_alarms = len(alarms)
    if total_alarms:
        logger.info(f"🚨 {total_alarms} fraud indicators found for claimant={claim.claimant_id}")
    else:
        logger.info(f"✅ No fraud indicators detected for claimant={claim.claimant_id}")

    return alarms


# =========================================================
# 🧪 Manual Test (Standalone Run)
# =========================================================
if __name__ == "__main__":
    from src.utils.db import engine
    from datetime import datetime as dt
    from sqlalchemy.orm import Session

    claim = ClaimData(
        amount=15000,
        report_delay_days=10,
        provider="Shady_Clinic",
        notes="Staged accident for quick cash, exaggerated injury.",
        claimant_id="repeat_user",
        location="Los Angeles, CA",
        timestamp=dt(2023, 10, 10, 3, 0),
        is_new_bank=True,
    )

    with engine.connect() as conn:
        db_session = Session(bind=conn)
        alarms = check_all_alarms(claim, db_session)

    print("\n=== 🚨 FRAUD ALARMS REPORT ===")
    for a in alarms:
        print("•", a)
    print(f"\nTotal: {len(alarms)} alarms")
