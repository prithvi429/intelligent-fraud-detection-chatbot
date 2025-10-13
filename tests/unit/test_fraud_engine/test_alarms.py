"""
Fraud Alarms Orchestrator
-------------------------
Runs all 13 fraud detection checks on a claim.

- 5 direct rule-based (legacy):
  Late reporting, new bank, out-of-network, blacklist, suspicious phrases.
- 8 modular (modern ML + rule hybrid):
  High amount, repeat claimant, suspicious keywords, location mismatch,
  duplicate claims, vendor fraud, time patterns, external mismatch.

Usage:
    raw_alarms = check_all_alarms(claim, db)
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from src.models.claim import ClaimData
from src.config import config
from src.utils.logger import logger
from src.utils.db import get_blacklist_providers
from src.nlp.text_analyzer import analyze_text

# ✅ Use relative imports for modular rules
from src.fraud_engine.rules.high_amount import check_high_amount
from src.fraud_engine.rules.repeat_claimant import check_repeat_claimant
from src.fraud_engine.rules.suspicious_keywords import check_suspicious_keywords
from src.fraud_engine.rules.location_mismatch import check_location_mismatch
from src.fraud_engine.rules.duplicate_claims import check_duplicate_claims
from src.fraud_engine.rules.vendor_fraud import check_vendor_fraud
from src.fraud_engine.rules.time_patterns import check_time_patterns
from src.fraud_engine.rules.external_mismatch import check_external_mismatch

# Suspicious phrases used by NLP and legacy text checks
SUSPICIOUS_PHRASES = [
    "late reporting", "new bank account", "out-of-network", "blacklist hit",
    "fake injury", "quick cash", "staged accident", "exaggerated pain",
    "ghost patient", "no witnesses", "cash only", "quick payout", "fake doctor"
]


# =====================================================
# 🧠 Main Orchestrator
# =====================================================
def check_all_alarms(claim: ClaimData, db: Optional[Session] = None) -> List[str]:
    """
    Run all fraud detection checks sequentially.
    Args:
        claim: ClaimData to analyze.
        db: Optional SQLAlchemy session.
    Returns:
        List[str]: All fraud alarm messages.
    """
    alarms: List[str] = []
    provider = (claim.provider or "").lower()
    notes = (claim.notes or "").strip().lower()

    logger.info(f"🧠 Running fraud detection for claimant={claim.claimant_id}, amount=${claim.amount:.2f}")

    # =====================================================
    # 🧩 ORIGINAL 5 RULES
    # =====================================================

    # 1️⃣ Late Reporting
    if getattr(claim, "report_delay_days", 0) > 7:
        alarms.append(
            f"[LATE-REPORT] Reported {claim.report_delay_days} days after incident (threshold: 7 days)"
        )

    # 2️⃣ New Bank Account
    if getattr(claim, "is_new_bank", False):
        alarms.append("[NEW-BANK] Payout to new/unverified bank account – verify claimant identity")

    # 3️⃣ Out-of-Network Provider
    if "out-of-network" in provider or "non-network" in provider:
        alarms.append(f"[OUT-NETWORK] Provider '{claim.provider}' not in approved insurer network")

    # 4️⃣ Blacklist Hit (DB or fallback)
    blacklist_providers = get_blacklist_providers(db) if db else ["shady_clinic", "fake_vendor"]
    for bl in blacklist_providers:
        if bl.lower() in provider:
            alarms.append(f"[BLACKLIST] Provider '{claim.provider}' matches blacklisted '{bl}'")
            break

    # 5️⃣ Suspicious Text Phrases (NLP)
    if notes:
        nlp_results = analyze_text(notes)
        matched = [p for p in SUSPICIOUS_PHRASES if p in notes] + nlp_results.get("suspicious_phrases", [])
        if matched:
            top_phrases = ", ".join(matched[:3])
            alarms.append(f"[TEXT-FLAG] Suspicious phrases ({len(matched)}): {top_phrases}")

    # =====================================================
    # ⚙️ NEW 8 RULES (MODULAR)
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
        logger.info(f"✅ No fraud detected for claimant={claim.claimant_id}")

    return alarms


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    from src.utils.db import engine
    from datetime import datetime as dt

    # Simulated high-risk claim
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
        print("\n=== FRAUD ALARMS REPORT ===")
        for a in alarms:
            print("•", a)
        print(f"\nTotal: {len(alarms)} alarms")
