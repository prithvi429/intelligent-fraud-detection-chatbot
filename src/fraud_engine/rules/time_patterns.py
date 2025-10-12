"""
Time Pattern Fraud Check
------------------------
Detects abnormal claim filing patterns such as:
- Submissions during unusual hours (2 AM – 5 AM)
- Rapid repeat claims (within 24 hours)
- Optional: Weekend filing (Saturday/Sunday)

Helps identify automation/bot activity and behavior anomalies.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.models.claim import ClaimData
from src.config import config
from src.utils.logger import logger
from datetime import datetime, timedelta

# Configurable constants
UNUSUAL_HOURS = (2, 3, 4, 5)       # Suspicious hours (2 AM – 5 AM)
MIN_GAP_HOURS = 24                 # Minimum gap between claims (hours)
CHECK_WEEKENDS = True              # Enable weekend check


def check_time_patterns(claim: ClaimData, db: Optional[Session] = None) -> List[str]:
    """
    Detects unusual filing times or submission patterns for claims.

    Args:
        claim (ClaimData): Current claim being analyzed.
        db (Session, optional): Database session for historical comparison.

    Returns:
        List[str]: Fraud alarms detected.
    """
    alarms: List[str] = []

    timestamp = getattr(claim, "timestamp", None)
    if not timestamp:
        logger.debug("[TIME-PATTERN] No timestamp provided – skipping check.")
        return alarms

    try:
        # Normalize to UTC (if naive)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=None)

        hour = timestamp.hour
        weekday = timestamp.strftime("%A")
        date = timestamp.date()

        # 1️⃣ Unusual filing hours (2–5 AM)
        if hour in UNUSUAL_HOURS:
            alarms.append(
                f"Time pattern fraud: Filed at {timestamp.strftime('%H:%M')} (unusual hour: {hour}:00 AM)"
            )
            logger.info(
                f"[TIME-PATTERN] 🚨 Unusual filing time detected for {claim.claimant_id}: {hour}:00 AM."
            )

        # 2️⃣ Weekend filing check (optional)
        if CHECK_WEEKENDS and weekday in ["Saturday", "Sunday"]:
            alarms.append(
                f"Time pattern fraud: Claim filed on {weekday} ({date}) – outside regular business days."
            )
            logger.debug(
                f"[TIME-PATTERN] Weekend submission for {claim.claimant_id}: {weekday}."
            )

        # 3️⃣ Too frequent submissions (<24h gap)
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
                    {"claimant_id": claim.claimant_id, "timestamp": timestamp},
                )
                last_claim_time = result.fetchone()
                if last_claim_time and last_claim_time[0]:
                    last_time = last_claim_time[0]
                    gap = (timestamp - last_time).total_seconds() / 3600  # Hours

                    if gap < MIN_GAP_HOURS:
                        alarms.append(
                            f"Time pattern fraud: Filed {gap:.1f} hours after previous claim on "
                            f"{last_time.date()} (threshold: {MIN_GAP_HOURS} hours)"
                        )
                        logger.info(
                            f"[TIME-PATTERN] 🚨 Rapid filing detected for {claim.claimant_id}: gap={gap:.1f}h."
                        )
            except Exception as e:
                logger.warning(f"[TIME-PATTERN] DB query failed for {claim.claimant_id}: {e}")
        else:
            logger.debug("[TIME-PATTERN] No DB session – skipping frequency check.")

        logger.debug(
            f"[TIME-PATTERN] Check summary for {claim.claimant_id}: hour={hour}, "
            f"weekday={weekday}, gap={gap if gap else 'N/A'}h"
        )

    except Exception as e:
        logger.error(f"[TIME-PATTERN] Unexpected error for {claim.claimant_id}: {e}")

    return alarms


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    from src.models.claim import ClaimData
    from datetime import datetime as dt

    # 1. Unusual hour test
    claim_odd = ClaimData(
        amount=5000,
        provider="ABC Hospital",
        claimant_id="user_demo",
        notes="",
        timestamp=dt(2023, 10, 10, 3, 0)  # 3 AM
    )
    print("🚨 Odd-hour alarms:", check_time_patterns(claim_odd))

    # 2. Weekend test
    claim_weekend = ClaimData(
        amount=7000,
        provider="XYZ Clinic",
        claimant_id="user_demo",
        notes="",
        timestamp=dt(2023, 10, 14, 11, 30)  # Saturday
    )
    print("🚨 Weekend alarms:", check_time_patterns(claim_weekend))
