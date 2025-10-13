"""
Location Mismatch Check
-----------------------
Detects suspicious location differences:
- Compares the claim’s incident location with claimant’s registered address.
- Uses geopy distance (cached via utils.external_apis).
- Triggers alarm if distance > configured threshold (e.g., 100 miles).

Example:
["[LOCATION-MISMATCH] 157.8 miles from registered address 'New York, NY' (threshold: 100 miles)"]
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.models.claim import ClaimData
from src.config import config
from src.utils.external_apis import calculate_location_distance
from src.utils.logger import logger


def check_location_mismatch(claim: ClaimData, db: Optional[Session] = None) -> List[str]:
    """
    Rule-based fraud detection for location mismatch.

    Args:
        claim (ClaimData): Input claim data with `location` field.
        db (Session, optional): SQLAlchemy session for registered address lookup.

    Returns:
        List[str]: Fraud alarm messages (if any).
    """
    alarms: List[str] = []

    # Extract location safely
    incident_location = (getattr(claim, "location", "") or "").strip()
    claimant_id = getattr(claim, "claimant_id", "unknown")

    if not incident_location:
        logger.debug("[LOCATION-MISMATCH] No incident location provided — skipping check.")
        return alarms

    # Default fallback (demo/test environments)
    registered_addr = "Unknown"
    try:
        if db:
            query = text("SELECT registered_address FROM claimants WHERE id = :claimant_id")
            result = db.execute(query, {"claimant_id": claimant_id})
            row = result.fetchone()
            if row and row[0]:
                registered_addr = row[0].strip()
            else:
                registered_addr = "New York, NY"
                logger.debug(f"[LOCATION-MISMATCH] No DB record for claimant {claimant_id} — using default.")
        else:
            registered_addr = "New York, NY"
            logger.debug("[LOCATION-MISMATCH] No DB session — using default mock address 'New York, NY'.")
    except Exception as e:
        logger.warning(f"[LOCATION-MISMATCH] ⚠️ DB query failed for claimant {claimant_id}: {e}")
        registered_addr = "New York, NY"

    # Calculate geographic distance (cached inside utility)
    try:
        distance = calculate_location_distance(incident_location, registered_addr)
    except Exception as e:
        logger.error(f"[LOCATION-MISMATCH] ❌ Distance calculation failed: {e}")
        return alarms

    if distance is None:
        logger.warning(f"[LOCATION-MISMATCH] Could not compute distance between '{incident_location}' and '{registered_addr}'.")
        return alarms

    threshold = getattr(config, "LOCATION_DISTANCE_THRESHOLD", 100.0)

    # 🚨 Trigger alarm if beyond threshold
    if distance > threshold:
        alarms.append(
            f"[LOCATION-MISMATCH] {distance:.1f} miles from registered address '{registered_addr}' "
            f"(threshold: {threshold:.0f} miles)."
        )
        logger.info(
            f"[LOCATION-MISMATCH] 🚨 Claimant '{claimant_id}' — {distance:.1f} miles apart "
            f"(limit: {threshold:.0f})."
        )
    else:
        logger.debug(
            f"[LOCATION-MISMATCH] ✅ Claimant '{claimant_id}' — within {distance:.1f} miles "
            f"of registered address."
        )

    return alarms


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    from src.models.claim import ClaimData

    claim = ClaimData(
        amount=5000,
        provider="ABC Insurance",
        claimant_id="user_demo",
        location="Los Angeles, CA",
        notes="Car accident reported away from home city."
    )

    print("\n🚨 Location Mismatch Alarms:")
    for alarm in check_location_mismatch(claim):
        print("•", alarm)
