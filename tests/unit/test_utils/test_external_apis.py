"""
External API Utilities
----------------------
Handles:
- Weather API (OpenWeatherMap)
- Vendor Fraud Check API
- Location Distance via geopy
Includes caching (cache_get / cache_set) and graceful fallbacks.
"""

import time
from datetime import datetime as dt
import requests
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from src.utils.cache import cache_get, cache_set
from src.utils.db import get_blacklist_providers
from src.config import config
from src.utils.logger import logger

# =========================================================
# 🌦 Weather API
# =========================================================
def check_weather_at_location(location: str, date_str: str = None):
    """
    Fetch current or recent historical weather using OpenWeatherMap.
    - Uses 'weather' endpoint for today/current
    - Uses 'onecall/timemachine' for <=5-day-old historical data
    - Returns dict or None on failure
    """
    cache_key = f"weather::{location}::{date_str}"
    if (cached := cache_get(cache_key)) is not None:
        return cached

    api_key = getattr(config, "WEATHER_API_KEY", None)
    if not api_key:
        logger.warning("No WEATHER_API_KEY configured.")
        return None

    try:
        # Parse date
        date_obj = dt.strptime(date_str, "%Y-%m-%d") if date_str else dt.utcnow()
    except Exception:
        logger.warning("Invalid date format provided to weather check.")
        return None

    today = dt.utcnow().date()
    days_diff = (today - date_obj.date()).days
    result = None

    try:
        if days_diff <= 0:
            # --- Current Weather ---
            resp = requests.get(
                "http://api.openweathermap.org/data/2.5/weather",
                params={"q": location, "appid": api_key, "units": "metric"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                result = {
                    "location": data.get("name", location),
                    "condition": data["weather"][0]["main"],
                    "temp": data["main"]["temp"],
                    "humidity": data["main"].get("humidity"),
                    "wind_speed": data["wind"]["speed"],
                    "is_rainy": "rain" in data["weather"][0]["main"].lower(),
                    "date": date_str or today.isoformat(),
                }
        elif 0 < days_diff <= 5:
            # --- Historical (<=5 days) ---
            geoloc = Nominatim(user_agent="fraud-engine").geocode(location, timeout=10)
            if not geoloc:
                logger.warning(f"Could not geocode location: {location}")
                return None
            timestamp = int(time.mktime(date_obj.timetuple()))
            resp = requests.get(
                "https://api.openweathermap.org/data/3.0/onecall/timemachine",
                params={
                    "lat": geoloc.latitude,
                    "lon": geoloc.longitude,
                    "dt": timestamp,
                    "appid": api_key,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                weather = data.get("weather", [{"main": "Unknown"}])[0]
                result = {
                    "condition": weather["main"],
                    "temp": data.get("main", {}).get("temp"),
                    "wind_speed": data.get("wind", {}).get("speed"),
                    "is_rainy": "rain" in weather["main"].lower(),
                    "date": date_str,
                }
        else:
            logger.warning("Historical data older than 5 days not available on free tier.")
            return None

        if result:
            cache_set(cache_key, result)
        else:
            logger.warning(f"Weather API call failed or returned empty result for {location}.")
        return result

    except Exception as e:
        logger.error(f"Weather API error for {location}: {e}")
        return None


# =========================================================
# 🏥 Vendor Fraud API
# =========================================================
def check_vendor_fraud(vendor_name: str, db=None):
    """
    Check vendor's fraud risk using external API or fallback to DB blacklist.
    - Returns dict: {is_fraudulent, risk_score, reason}
    - Caches results per vendor.
    """
    cache_key = f"vendor::{vendor_name}"
    if (cached := cache_get(cache_key)) is not None:
        return cached

    api_url = getattr(config, "VENDOR_CHECK_API_URL", None)
    if not api_url:
        logger.warning("VENDOR_CHECK_API_URL not set. Using blacklist fallback.")
        return _vendor_blacklist_fallback(vendor_name, db)

    try:
        resp = requests.get(api_url, params={"vendor": vendor_name}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            result = {
                "vendor": data.get("vendor", vendor_name),
                "is_fraudulent": data.get("is_fraudulent", False),
                "risk_score": data.get("risk_score", 0.0),
                "reason": data.get("reason", "Unknown"),
            }
            cache_set(cache_key, result)
            return result
        else:
            # API failure → fallback
            return _vendor_blacklist_fallback(vendor_name, db)
    except Exception as e:
        logger.error(f"Vendor fraud API error for {vendor_name}: {e}")
        return _vendor_blacklist_fallback(vendor_name, db)


def _vendor_blacklist_fallback(vendor_name: str, db=None):
    """Check DB blacklist fallback for vendor risk."""
    try:
        blacklisted = get_blacklist_providers(db)
    except Exception:
        blacklisted = []

    if blacklisted and vendor_name in blacklisted:
        result = {
            "vendor": vendor_name,
            "is_fraudulent": True,
            "risk_score": 0.9,
            "reason": "Blacklist match",
        }
    else:
        result = {
            "vendor": vendor_name,
            "is_fraudulent": False,
            "risk_score": 0.0,
            "reason": "Clean or no data",
        }

    cache_set(f"vendor::{vendor_name}", result)
    return result


# =========================================================
# 📍 Location Distance via geopy
# =========================================================
def calculate_location_distance(addr1: str, addr2: str):
    """
    Calculate distance (in miles) between two addresses using geopy.
    - Caches geocode results for addresses and final distance.
    - Returns None on error.
    """
    cache_key = f"distance::{addr1}::{addr2}"
    if (cached := cache_get(cache_key)) is not None:
        return cached

    try:
        geo_cache1 = f"geocode::{addr1}"
        geo_cache2 = f"geocode::{addr2}"
        geoloc1 = cache_get(geo_cache1)
        geoloc2 = cache_get(geo_cache2)

        geolocator = Nominatim(user_agent="fraud-engine")

        if not geoloc1:
            loc1 = geolocator.geocode(addr1, timeout=10)
            if not loc1:
                return None
            geoloc1 = (loc1.latitude, loc1.longitude)
            cache_set(geo_cache1, geoloc1)

        if not geoloc2:
            loc2 = geolocator.geocode(addr2, timeout=10)
            if not loc2:
                return None
            geoloc2 = (loc2.latitude, loc2.longitude)
            cache_set(geo_cache2, geoloc2)

        distance_miles = geodesic(geoloc1, geoloc2).miles
        cache_set(cache_key, distance_miles)
        return distance_miles

    except Exception as e:
        logger.warning(f"Location distance calculation failed: {e}")
        return None
