"""
External Data Mismatch Check
----------------------------
Validates claim context (e.g., weather, environment) against external APIs.

- Uses OpenWeatherMap via `check_weather_at_location()` to confirm incident plausibility.
- Detects mismatches like:
  - "accident/slip" claims made on clear weather days.
  - "cold injury" claims during warm temperatures.
- Caches weather data to minimize API calls.

Example:
["[EXTERNAL-MISMATCH] Weather-sensitive claim ('accident') during clear weather on 2023-10-01 at Mumbai, India."]
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from src.models.claim import ClaimData
from src.utils.external_apis import check_weather_at_location
from src.utils.logger import logger

# =========================================================
# 🌦 Configuration Constants
# =========================================================
WEATHER_SENSITIVE_KEYWORDS = [
    "accident", "slip", "fall", "storm", "rain", "wet", "flood", "hail", "wind"
]

COLD_TEMP_THRESHOLD = 20  # °C
RAIN_REQUIRED = True


# =========================================================
# ⚙️ Rule Function
# =========================================================
def check_external_mismatch(claim: ClaimData, db: Optional[Session] = None) -> List[str]:
    """
    Cross-verifies claim details against external (weather) data.

    Args:
        claim (ClaimData): Claim with `notes`, `location`, `timestamp`.
        db (Session, optional): Reserved for future use (multi-API integration).

    Returns:
        List[str]: Fraud alarm messages if mismatches are detected.
    """
    alarms: List[str] = []

    # ✅ Extract claim attributes safely
    notes = (claim.notes or "").lower()
    location = (claim.location or "").strip()
    claim_date = (
        claim.timestamp.strftime("%Y-%m-%d")
        if getattr(claim, "timestamp", None)
        else datetime.now().strftime("%Y-%m-%d")
    )

    # 🚫 Skip checks if not applicable
    if not location:
        logger.debug("[EXTERNAL-MISMATCH] Missing location — skipping check.")
        return alarms

    if not any(keyword in notes for keyword in WEATHER_SENSITIVE_KEYWORDS):
        logger.debug(f"[EXTERNAL-MISMATCH] No weather-related keywords in notes for {claim.claimant_id}.")
        return alarms

    try:
        # 🌤 Fetch weather data from cached API utility
        weather_data = check_weather_at_location(location, claim_date)

        if not weather_data:
            logger.warning(f"[EXTERNAL-MISMATCH] Weather data unavailable for {location} on {claim_date}.")
            return alarms

        # 🌡️ Extract weather context
        condition = weather_data.get("condition", "unknown").lower()
        is_rainy = bool(weather_data.get("is_rainy", False))
        temp = weather_data.get("temp")

        triggered_keyword = next((k for k in WEATHER_SENSITIVE_KEYWORDS if k in notes), "weather event")

        # ⚠️ Case 1: Weather-sensitive claim but clear weather
        if RAIN_REQUIRED and not is_rainy:
            alarms.append(
                f"[EXTERNAL-MISMATCH] Weather-sensitive claim ('{triggered_keyword}') "
                f"during {condition} weather on {claim_date} at {location}."
            )
            logger.info(
                f"[EXTERNAL-MISMATCH] 🚨 Mismatch for claimant={claim.claimant_id}: "
                f"'{triggered_keyword}' but weather='{condition}'."
            )

        # ⚠️ Case 2: 'Cold injury' claimed during warm weather
        if "cold" in notes and temp is not None and temp > COLD_TEMP_THRESHOLD:
            alarms.append(
                f"[EXTERNAL-MISMATCH] 'Cold injury' claimed but temperature was "
                f"{temp:.1f}°C on {claim_date} at {location}."
            )
            logger.info(
                f"[EXTERNAL-MISMATCH] 🚨 Temperature mismatch for claimant={claim.claimant_id}: {temp:.1f}°C."
            )

        logger.debug(
            f"[EXTERNAL-MISMATCH] Weather={condition}, temp={temp}, rainy={is_rainy} "
            f"for {location} on {claim_date}."
        )

    except Exception as e:
        logger.error(f"[EXTERNAL-MISMATCH] Error checking weather for {location}: {e}")

    return alarms


# =========================================================
# 🧪 Manual Test (Standalone)
# =========================================================
if __name__ == "__main__":
    from datetime import datetime as dt
    from src.models.claim import ClaimData

    claim = ClaimData(
        amount=8000,
        provider="CarePoint Hospital",
        claimant_id="demo_user",
        notes="Car accident on slippery road due to rain.",
        location="Mumbai, India",
        timestamp=dt(2023, 10, 10),
    )

    print("\n🚨 External Mismatch Alarms:")
    for alarm in check_external_mismatch(claim):
        print("•", alarm)
