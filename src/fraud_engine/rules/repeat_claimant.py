"""
Repeat Claimant Check
---------------------
Detects users who file frequent claims (e.g., more than 3 claims in the past 12 months).

Why:
- High frequency of claims can indicate staged or habitual fraud.
- Used as a rule-based signal for review or rejection.

Returns:
    List[str] – e.g., ["[REPEAT-CLAIM] 4 prior claims in the last 12 months"]
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.models.claim import ClaimData
from src.config import config
from src.utils.logger import logger


def check_repeat_claimant(claim: ClaimData, db: Optional[Session] = None) -> List[str]:
    """
    Rule-based fraud detection: Repeat Claimant Check.

    Args:
        claim (ClaimData): Claim input object.
        db (Session, optional): SQLAlchemy session to query historical claims.

    Returns:
        List[str]: Fraud alarm messages if threshold exceeded.
    """
    alarms: List[str] = []
    claimant_id = getattr(claim, "claimant_id", "unknown")

    # 🚫 If DB unavailable, skip rule
    if not db:
        logger.debug("[REPEAT-CLAIM] No DB session provided — skipping check.")
        return alarms

    months_window = 12
    threshold = getattr(config, "REPEAT_CLAIM_THRESHOLD", 3)

    try:
        # ✅ Cross-compatible query (works in SQLite + PostgreSQL)
        sql = text("""
            SELECT COUNT(*) 
            FROM claims
            WHERE claimant_id = :claimant_id
              AND (
                    created_at >= DATE('now', :minus_window)
                    OR created_at >= (CURRENT_TIMESTAMP - INTERVAL '12 months')
                  )
        """)
        params = {"claimant_id": claimant_id, "minus_window": f"-{months_window} months"}
        result = db.execute(sql, params)
        claim_count = int(result.scalar() or 0)

        logger.debug(f"[REPEAT-CLAIM] {claimant_id}: {claim_count} claims in last {months_window} months.")

        # 🚨 Trigger alarm if over threshold
        if claim_count >= threshold:
            plural = "s" if claim_count != 1 else ""
            alarms.append(
                f"[REPEAT-CLAIM] {claim_count} prior claim{plural} in the last "
                f"{months_window} months (threshold: {threshold})."
            )
            logger.info(
                f"[REPEAT-CLAIM] 🚨 Repeat claimant detected — {claimant_id}: {claim_count} claims."
            )

    except Exception as e:
        logger.warning(f"[REPEAT-CLAIM] ⚠️ DB query failed for {claimant_id}: {e}")

    if not alarms:
        logger.debug(f"[REPEAT-CLAIM] ✅ Claimant {claimant_id} has no suspicious claim frequency.")

    return alarms


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    from src.models.claim import ClaimData
    from src.utils.db import SessionLocal

    test_claim = ClaimData(
        amount=5000,
        provider="ABC Health",
        claimant_id="repeat_user_1",
        notes="Follow-up claim for ongoing injury"
    )

    with SessionLocal() as db:
        alarms = check_repeat_claimant(test_claim, db)
        print("\n🚨 Repeat Claimant Alarms:")
        for alarm in alarms:
            print("•", alarm)
