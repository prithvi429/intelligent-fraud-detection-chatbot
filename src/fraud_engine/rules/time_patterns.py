"""
Time Pattern Fraud Check
------------------------
Detects abnormal claim filing patterns such as:
- Submissions during unusual hours (2 AM – 5 AM)
- Rapid repeat claims (within 24 hours)
- Weekend submissions (optional)

Helps identify automation/bot activity and behavioral anomalies.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from src.models.claim import ClaimData
from src.config import config
from src.utils.logger import logger

# Configurable thresholds (fallbacks)
UNUSUAL_HOURS = getattr(config, "UNUSUAL_HOURS", (2, 3, 4, 5))  # Suspicious hours (2 AM – 5 AM)
MIN_GAP_HOURS = getattr(config, "MIN_GAP_HOURS", 24)            # Minimum gap between claims
CHECK_WEEKENDS = getattr(config, "CHECK_WEEKENDS", True)        # Enable weekend flagging


def check_time_patterns(claim: ClaimData, db: Optional[Session] = None) -> List[str]:
    """
    Detects unusual filing hours, weekend submissions, or rapid repeat claims.

    Args:
        claim (ClaimData): Claim under analysis.
        db (Session, optional): Database session for checking recent claim times.

    Returns:
        List[str]: Fraud alarm messages, if any detected.
    """
    alarms: List[str] = []
    claimant_id = getattr(claim, "claimant_id", "unknown")
    timestamp = getattr(claim, "timestamp", None)

    if not timestamp:
        logger.debug("[TIME-PATTERN] No timestamp provided — skipping temporal analysis.")
        return alarms

    try:
        # Normalize timestamp (ensure naive datetime handled)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.replace(tzinfo=None)

        hour = timestamp.hour
        weekday = timestamp.strftime("%A")
        date = timestamp.date()

        # 1️⃣ Unusual filing hours (e.g., 2 AM – 5 AM)
        if hour in UNUSUAL_HOURS:
            alarms.append(
                f"[TIME-PATTERN] Filed at {timestamp.strftime('%H:%M')} "
                f"(unusual hour: {hour}:00 AM)."
            )
            logger.info(f"[TIME-PATTERN] 🚨 Odd filing hour detected — {claimant_id}: {hour}:00 AM.")

        # 2️⃣ Weekend submission
        if CHECK_WEEKENDS and weekday in {"Saturday", "Sunday"}:
            alarms.append(
                f"[TIME-PATTERN] Claim filed on {weekday} ({date}) — outside standard business days."
            )
            logger.debug(f"[TIME-PATTERN] Weekend filing detected for {claimant_id}: {weekday}.")

        # 3️⃣ Rapid repeat submissions (< 24h gap)
        gap = None
        if db:
            try:
                result = db.execute(
                    text("""
                        SELECT created_at 
                        FROM claims 
                        WHERE claimant_id = :claimant_id 
                          AND created_at < :timestamp
                        ORDER BY created_at DESC 
                        LIMIT 1
                    """),
                    {"claimant_id": claimant_id, "timestamp": timestamp},
                )
                row = result.fetchone()
                if row and row[0]:
                    last_time = row[0]
                    gap = (timestamp - last_time).total_seconds() / 3600

                    if gap < MIN_GAP_HOURS:
                        alarms.append(
                            f"[TIME-PATTERN] Filed {gap:.1f} hours after previous claim on "
                            f"{last_time.date()} (threshold: {MIN_GAP_HOURS}h)."
                        )
                        logger.info(
                            f"[TIME-PATTERN] 🚨 Rapid filing — {claimant_id}: gap={gap:.1f}h (<{MIN_GAP_HOURS}h)."
                        )
            except Exception as e:
                logger.warning(f"[TIME-PATTERN] ⚠️ DB lookup failed for {claimant_id}: {e}")
        else:
            logger.debug("[TIME-PATTERN] No DB connection — skipping frequency check.")

        logger.debug(
            f"[TIME-PATTERN] Summary for {claimant_id}: hour={hour}, weekday={weekday}, gap={gap or 'N/A'}h"
        )

    except Exception as e:
        logger.error(f"[TIME-PATTERN] ❌ Unexpected error during time pattern analysis for {claimant_id}: {e}")

    return alarms


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    from src.models.claim import ClaimData
    from datetime import datetime as dt

    # 1️⃣ Test unusual hour
    claim_odd = ClaimData(
        amount=5000,
        provider="ABC Hospital",
        claimant_id="user_demo",
        notes="Filed early morning",
        timestamp=dt(2023, 10, 10, 3, 0),  # 3 AM
    )
    print("\n🚨 Odd-hour alarms:", check_time_patterns(claim_odd))

    # 2️⃣ Test weekend filing
    claim_weekend = ClaimData(
        amount=7000,
        provider="XYZ Clinic",
        claimant_id="user_demo",
        notes="Filed over the weekend",
        timestamp=dt(2023, 10, 14, 11, 30),  # Saturday
    )
    print("🚨 Weekend alarms:", check_time_patterns(claim_weekend))
