"""
Location Mismatch Check
-----------------------
Detects suspicious location differences:
- Compares the claim’s incident location with claimant’s registered address.
- Uses geopy distance (cached via utils.external_apis).
- Triggers alarm if distance > configured threshold (e.g., 100 miles).

Output Example:
["Location mismatch: 157.8 miles from registered address 'New York, NY' (threshold: 100 miles)"]
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
        List[str]: Fraud alarm messages.
    """
    alarms: List[str] = []

    # Safe access
    incident_location = (claim.location or "").strip()
    if not incident_location:
        logger.debug("[LOCATION-MISMATCH] No incident location provided — skipping check.")
        return alarms

    # Default fallback address
    registered_addr = "Unknown"
    if db:
        try:
            result = db.execute(
                text("SELECT registered_address FROM claimants WHERE id = :claimant_id"),
                {"claimant_id": claim.claimant_id}
            )
            row = result.fetchone()
            if row and row[0]:
                registered_addr = row[0].strip()
            else:
                registered_addr = "New York, NY"  # Default for test/demo
                logger.debug(f"[LOCATION-MISMATCH] No DB address for {claim.claimant_id} — using default.")
        except Exception as e:
            logger.warning(f"[LOCATION-MISMATCH] DB query failed for claimant {claim.claimant_id}: {e}")
            registered_addr = "New York, NY"
    else:
        logger.debug("[LOCATION-MISMATCH] No DB session — using mock address 'New York, NY'.")
        registered_addr = "New York, NY"

    # Calculate distance (cached)
    distance = calculate_location_distance(incident_location, registered_addr)

    if distance is None:
        logger.warning(f"[LOCATION-MISMATCH] Could not calculate distance between '{incident_location}' and '{registered_addr}'.")
        return alarms

    # Threshold comparison
    if distance > config.LOCATION_DISTANCE_THRESHOLD:
        alarm_text = (
            f"Location mismatch: {distance:.1f} miles from registered address "
            f"'{registered_addr}' (threshold: {config.LOCATION_DISTANCE_THRESHOLD} miles)."
        )
        alarms.append(alarm_text)
        logger.debug(f"[LOCATION-MISMATCH] 🚨 Triggered alarm for {claim.claimant_id}: {distance:.1f} miles apart.")
    else:
        logger.debug(f"[LOCATION-MISMATCH] OK — {incident_location} within {distance:.1f} miles of '{registered_addr}'.")

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

    print("🚨 Alarms:", check_location_mismatch(claim))
