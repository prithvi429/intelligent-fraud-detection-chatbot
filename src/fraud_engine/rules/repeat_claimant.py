"""
Repeat Claimant Check
---------------------
Detects users who file frequent claims (e.g., more than 3 claims in the past 12 months).

Why:
- High frequency of claims can indicate staged or habitual fraud.
- Used as a rule-based signal for review or rejection.

Returns:
    List[str] – e.g., ["Repeat claimant: 4 claims in the last 12 months"]
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
        claim (ClaimData): Claim input.
        db (Session, optional): SQLAlchemy session.

    Returns:
        List[str]: Fraud alarms detected.
    """
    alarms: List[str] = []

    if not db:
        logger.debug("[REPEAT-CLAIM] No DB session provided – skipping check.")
        return alarms

    months = 12  # time window
    try:
        # Portable SQL for PostgreSQL + SQLite
        sql = text("""
            SELECT COUNT(*) FROM claims
            WHERE claimant_id = :claimant_id
              AND (
                created_at >= (
                  CASE
                    WHEN CURRENT_TIMESTAMP IS NOT NULL THEN CURRENT_TIMESTAMP - INTERVAL '12 months'
                    ELSE datetime('now', '-12 months')
                  END
                )
              )
        """)
        result = db.execute(sql, {"claimant_id": claim.claimant_id})
        count = int(result.scalar() or 0)

        logger.debug(f"[REPEAT-CLAIM] {claim.claimant_id} has {count} prior claims in last {months} months.")

        # Apply rule threshold
        if count >= config.REPEAT_CLAIM_THRESHOLD:
            plural = "s" if count != 1 else ""
            alarms.append(
                f"Repeat claimant: {count} prior claim{plural} in the last {months} months "
                f"(threshold = {config.REPEAT_CLAIM_THRESHOLD})."
            )

    except Exception as e:
        logger.warning(f"[REPEAT-CLAIM] DB query failed for {claim.claimant_id}: {e}")

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
        print("🚨 Alarms:", alarms)
