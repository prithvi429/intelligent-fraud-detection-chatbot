"""
High Claim Amount Check
-----------------------
Flags claims with unusually high amounts based on:

1️⃣ Absolute threshold (from config, e.g., > $10,000)
2️⃣ Relative threshold (e.g., > 3× claimant’s historical average)

Purpose:
- Detect inflated or outlier claim amounts.
- Provide signal for fraud scoring and explainability.

Returns:
    List[str]: e.g., ["[HIGH-AMOUNT] $15,000 exceeds threshold ($10,000)"]
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.models.claim import ClaimData
from src.config import config
from src.utils.logger import logger


def check_high_amount(claim: ClaimData, db: Optional[Session] = None) -> List[str]:
    """
    Rule-based + data-driven check for high-amount claims.

    Args:
        claim (ClaimData): Claim input data.
        db (Session, optional): SQLAlchemy session for historical lookup.

    Returns:
        List[str]: List of descriptive fraud alarm messages.
    """
    alarms: List[str] = []
    amount = float(getattr(claim, "amount", 0.0) or 0.0)
    claimant_id = getattr(claim, "claimant_id", "unknown")

    # =========================================================
    # 1️⃣ Absolute Threshold Check
    # =========================================================
    threshold = getattr(config, "HIGH_AMOUNT_THRESHOLD", 10000.0)
    if amount > threshold:
        alarms.append(
            f"[HIGH-AMOUNT] Claim value ${amount:,.2f} exceeds static threshold (${threshold:,.2f})."
        )
        logger.info(f"[HIGH-AMOUNT] 🚨 {claimant_id}: ${amount:.2f} > threshold ${threshold:.2f}")

    # =========================================================
    # 2️⃣ Relative Check — vs Claimant’s Historical Average
    # =========================================================
    if db:
        try:
            # Works for SQLite & PostgreSQL
            sql = text("""
                SELECT AVG(amount)
                FROM claims
                WHERE claimant_id = :claimant_id
                  AND amount > 0
                  AND (
                        created_at >= DATE('now', '-12 months') 
                        OR created_at >= (CURRENT_TIMESTAMP - INTERVAL '12 months')
                      )
            """)

            result = db.execute(sql, {"claimant_id": claimant_id})
            avg_amount = result.scalar() or 0.0

            if avg_amount > 0 and amount > 3 * avg_amount:
                ratio = amount / avg_amount
                alarms.append(
                    f"[HIGH-AMOUNT] Claim ${amount:,.2f} is {ratio:.1f}× higher than "
                    f"12-month claimant average (${avg_amount:,.2f})."
                )
                logger.info(
                    f"[HIGH-AMOUNT] 🚨 Outlier detected: {claimant_id}, Avg=${avg_amount:.2f}, "
                    f"Current=${amount:.2f}, Ratio={ratio:.2f}"
                )
            else:
                logger.debug(
                    f"[HIGH-AMOUNT] {claimant_id}: Avg=${avg_amount:.2f}, Current=${amount:.2f} — within range."
                )

        except Exception as e:
            logger.warning(f"[HIGH-AMOUNT] ⚠️ DB lookup failed for {claimant_id}: {e}")

    else:
        logger.debug(f"[HIGH-AMOUNT] No DB session — skipping average check for {claimant_id}")

    # =========================================================
    # ✅ Final Summary
    # =========================================================
    if not alarms:
        logger.debug(f"[HIGH-AMOUNT] {claimant_id}: ${amount:.2f} appears normal.")

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

    print("\n🚨 High Amount Alarms:")
    for alarm in check_high_amount(test_claim):
        print("•", alarm)
