"""
High Claim Amount Check
-----------------------
Flags claims with unusually high amounts — either:
1️⃣ Absolute threshold (from config, e.g., > $10,000)
2️⃣ Relative threshold (e.g., > 3× claimant’s historical average)

Purpose:
- Detect inflated or outlier claim amounts.
- Feed signal to fraud engine and decision logic.

Returns:
    List[str]: e.g., ["High claim amount: $15,000 exceeds threshold ($10,000)"]
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.models.claim import ClaimData
from src.config import config
from src.utils.logger import logger


def check_high_amount(claim: ClaimData, db: Optional[Session] = None) -> List[str]:
    """
    Rule-based + data-driven high-amount fraud check.

    Args:
        claim (ClaimData): Claim input data.
        db (Session, optional): SQLAlchemy session for DB query.

    Returns:
        List[str]: Descriptive alarm messages.
    """
    alarms: List[str] = []
    amount = float(claim.amount or 0.0)

    # 1️⃣ Absolute threshold check
    if amount > config.HIGH_AMOUNT_THRESHOLD:
        alarms.append(
            f"High claim amount: ${amount:,.2f} exceeds threshold (${config.HIGH_AMOUNT_THRESHOLD:,.2f})."
        )
        logger.debug(f"[HIGH-AMOUNT] {claim.claimant_id}: Exceeds static threshold (${config.HIGH_AMOUNT_THRESHOLD})")

    # 2️⃣ Relative outlier vs claimant’s history
    if db:
        try:
            # Portable query (works with PostgreSQL & SQLite)
            sql = text("""
                SELECT AVG(amount)
                FROM claims
                WHERE claimant_id = :claimant_id
                  AND created_at >= (
                    CASE
                      WHEN CURRENT_TIMESTAMP IS NOT NULL THEN CURRENT_TIMESTAMP - INTERVAL '12 months'
                      ELSE datetime('now', '-12 months')
                    END
                  )
            """)
            result = db.execute(sql, {"claimant_id": claim.claimant_id})
            avg_amount = result.scalar() or 0.0

            if avg_amount > 0 and amount > 3 * avg_amount:
                ratio = amount / avg_amount
                alarms.append(
                    f"High claim amount: ${amount:,.2f} is {ratio:.1f}× your 12-month average (${avg_amount:,.2f})."
                )
                logger.debug(f"[HIGH-AMOUNT] {claim.claimant_id}: Avg=${avg_amount:.2f}, Current=${amount:.2f}, Ratio={ratio:.2f}")

        except Exception as e:
            logger.warning(f"[HIGH-AMOUNT] DB lookup failed for {claim.claimant_id}: {e}")

    else:
        logger.debug(f"[HIGH-AMOUNT] No DB provided — skipping history check for {claim.claimant_id}")

    if not alarms:
        logger.debug(f"[HIGH-AMOUNT] {claim.claimant_id}: Amount ${amount:.2f} appears normal.")

    return alarms


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    from src.models.claim import ClaimData

    test_claim = ClaimData(
        amount=15000,
        provider="ABC Hospital",
        claimant_id="user123",
        notes="Minor accident"
    )

    print("🚨 Alarms:", check_high_amount(test_claim))
