"""
External APIs Utility
---------------------
Handles integrations for:
🌦️ Weather data validation (OpenWeatherMap)
🏥 Vendor fraud verification (external API + DB fallback)
📍 Geolocation / distance checks (Nominatim via Geopy)
Includes Redis/in-memory caching for performance and fault tolerance.
"""

import requests
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from typing import Optional, Dict, Any
from datetime import datetime
from src.config import config
from src.utils.logger import logger
from src.utils.cache import cache_get, cache_set
from src.utils.db import get_blacklist_providers

# =========================================================
# 🌦️ WEATHER VALIDATION
# =========================================================
def check_weather_at_location(location: str, date: str) -> Optional[Dict[str, Any]]:
    """
    Validate whether the weather data at a location matches claim conditions.
    Example: A “storm damage” claim but weather shows “Clear”.
    - Caches result for 1h (current) or 24h (historical)
    - Uses OpenWeatherMap API (current + limited 5-day history)
    """
    cache_key = f"weather:{location}:{date}"
    cached = cache_get(cache_key)
    if cached:
        logger.debug(f"Cache hit for weather: {cache_key}")
        return cached

    if not config.WEATHER_API_KEY:
        logger.warning("No WEATHER_API_KEY found — skipping weather check.")
        return None

    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        today = datetime.now().date()
        days_diff = (today - target_date).days

        if days_diff < 0:
            logger.warning(f"Date {date} is in the future — weather check skipped.")
            return None

        # Select endpoint: current vs historical
        if days_diff == 0:
            url = "http://api.openweathermap.org/data/2.5/weather"
            params = {"q": location, "appid": config.WEATHER_API_KEY, "units": "metric"}
            expire = 3600
        elif days_diff <= 5:
            # Historical API requires lat/lon
            geoloc = Nominatim(user_agent="fraud_weather_bot").geocode(location)
            if not geoloc:
                logger.warning(f"Could not geocode location: {location}")
                return None
            timestamp = int(datetime.combine(target_date, datetime.min.time()).timestamp())
            url = "https://api.openweathermap.org/data/3.0/onecall/timemachine"
            params = {"lat": geoloc.latitude, "lon": geoloc.longitude, "dt": timestamp, "appid": config.WEATHER_API_KEY, "units": "metric"}
            expire = 86400
        else:
            logger.info(f"Historical weather unavailable (>5 days): {date}")
            return None

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Normalize output
        weather_info = (
            data["weather"][0] if "weather" in data else data.get("current", {}).get("weather", [{}])[0]
        )

        result = {
            "location": location,
            "date": date,
            "condition": weather_info.get("main", "Unknown"),
            "description": weather_info.get("description", ""),
            "temp": data.get("main", {}).get("temp", data.get("current", {}).get("temp")),
            "wind_speed": data.get("wind", {}).get("speed", 0),
            "humidity": data.get("main", {}).get("humidity", 0),
            "is_rainy": "Rain" in weather_info.get("main", ""),
        }

        cache_set(cache_key, result, expire_seconds=expire)
        logger.debug(f"🌦️ Weather data cached for {location} ({result['condition']})")
        return result

    except Exception as e:
        logger.warning(f"⚠️ Weather check failed for {location} on {date}: {e}")
        return None


# =========================================================
# 🏥 VENDOR FRAUD CHECK
# =========================================================
def check_vendor_fraud(vendor_name: str, db_session=None) -> Dict[str, Any]:
    """
    Check vendor fraud risk from API or DB fallback.
    Returns dict:
      {vendor, is_fraudulent, risk_score, reason, source}
    Cache: 24h.
    """
    vendor_lower = vendor_name.lower().strip()
    cache_key = f"vendor:{vendor_lower}"
    cached = cache_get(cache_key)
    if cached:
        logger.debug(f"Cache hit for vendor: {vendor_lower}")
        return cached

    try:
        # 🔹 1. Try external VendorCheck API
        if config.VENDOR_CHECK_API_URL:
            resp = requests.get(
                f"{config.VENDOR_CHECK_API_URL}/check",
                params={"vendor": vendor_name},
                headers={"User-Agent": "FraudDetectionBot/1.0"},
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                result = {
                    "vendor": vendor_name,
                    "is_fraudulent": data.get("is_fraudulent", False),
                    "risk_score": data.get("risk_score", 0.0),
                    "reason": data.get("reason", "Verified via API"),
                    "source": "external_api",
                }
                cache_set(cache_key, result, expire_seconds=86400)
                return result
            logger.warning(f"Vendor API returned {resp.status_code} for {vendor_name}")

        # 🔹 2. Fallback — internal DB blacklist
        if db_session:
            blacklisted = get_blacklist_providers(db_session)
            is_fraud = vendor_lower in [p.lower() for p in blacklisted]
            result = {
                "vendor": vendor_name,
                "is_fraudulent": is_fraud,
                "risk_score": 0.95 if is_fraud else 0.0,
                "reason": "Internal blacklist" if is_fraud else "Not in blacklist",
                "source": "internal_db",
            }
            cache_set(cache_key, result, expire_seconds=86400)
            return result

        return {"vendor": vendor_name, "is_fraudulent": False, "risk_score": 0.0, "reason": "No data", "source": "none"}

    except Exception as e:
        logger.error(f"❌ Vendor check error for {vendor_name}: {e}")
        return {"vendor": vendor_name, "is_fraudulent": False, "risk_score": 0.0, "reason": "Error occurred", "source": "error"}


# =========================================================
# 📍 GEOLOCATION CHECK
# =========================================================
def calculate_location_distance(addr1: str, addr2: str) -> Optional[float]:
    """
    Calculate distance (miles) between two addresses using Geopy (Nominatim).
    - Uses caching for geocodes (1h)
    - Handles failures gracefully (returns None)
    """
    cache_key = f"distance:{addr1}:{addr2}"
    cached = cache_get(cache_key)
    if cached:
        logger.debug(f"Cache hit for distance: {addr1} → {addr2}")
        return cached

    try:
        geolocator = Nominatim(user_agent="fraud_detection_bot", timeout=10)

        def get_or_cache_geocode(addr: str):
            key = f"geocode:{addr}"
            cached_geo = cache_get(key)
            if cached_geo:
                return cached_geo
            geo = geolocator.geocode(addr)
            if not geo:
                return None
            coords = {"latitude": geo.latitude, "longitude": geo.longitude}
            cache_set(key, coords, expire_seconds=3600)
            return coords

        loc1 = get_or_cache_geocode(addr1)
        loc2 = get_or_cache_geocode(addr2)
        if not loc1 or not loc2:
            logger.warning(f"⚠️ Geocode failed for '{addr1}' or '{addr2}'")
            return None

        distance = geodesic(
            (loc1["latitude"], loc1["longitude"]),
            (loc2["latitude"], loc2["longitude"]),
        ).miles

        cache_set(cache_key, distance, expire_seconds=3600)
        logger.debug(f"📍 Distance between '{addr1}' and '{addr2}': {distance:.2f} miles")
        return distance
    except Exception as e:
        logger.error(f"❌ Location distance error ({addr1} → {addr2}): {e}")
        return None


# =========================================================
# 🧪 Local Testing
# =========================================================
if __name__ == "__main__":
    from src.utils.db import SessionLocal
    db = next(SessionLocal())

    print("🌦️ Weather:", check_weather_at_location("Mumbai, India", datetime.now().strftime("%Y-%m-%d")))
    print("🏥 Vendor:", check_vendor_fraud("shady_clinic", db))
    print("📍 Distance:", calculate_location_distance("Pune, India", "Mumbai, India"))
