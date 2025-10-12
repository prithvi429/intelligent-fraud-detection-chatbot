"""
Cache Utility
-------------
Handles Redis + in-memory fallback for caching fraud scores, NLP results, and external API responses.
Optimized for FastAPI async workloads and safe in local/AWS setups.
"""

import redis
import json
import threading
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
from src.config import config
from src.utils.logger import logger

# =========================================================
# 🧠 In-memory fallback
# =========================================================
_cache_store: Dict[str, Any] = {}
_cache_lock = threading.Lock()

# =========================================================
# 🔌 Redis Connection
# =========================================================
try:
    r = redis.from_url(config.REDIS_URL, decode_responses=True, socket_timeout=3)
    r.ping()  # Test connectivity
    USE_REDIS = True
    logger.info("✅ Redis connected successfully. Caching enabled.")
except Exception as e:
    r = None
    USE_REDIS = False
    logger.warning(f"⚠️ Redis unavailable ({e}). Using local in-memory cache instead.")

# =========================================================
# 🧰 JSON Safe Serialization
# =========================================================
def safe_json_dumps(data: Any) -> str:
    """Safely convert data to JSON (handles datetime)."""
    def default(o):
        if isinstance(o, datetime):
            return o.isoformat()
        return str(o)
    return json.dumps(data, default=default)


# =========================================================
# 🧩 Core Cache Functions
# =========================================================
def cache_get(key: str) -> Optional[Any]:
    """Get cached value by key, checking expiration."""
    if USE_REDIS and r:
        try:
            value = r.get(key)
            if value:
                logger.debug(f"⚡ Cache hit (Redis): {key}")
                return json.loads(value)
            return None
        except Exception as e:
            logger.debug(f"Cache get failed for {key}: {e}")
            return None

    # Local fallback
    with _cache_lock:
        entry = _cache_store.get(key)
        if entry:
            value, expire_time = entry
            if datetime.now() < expire_time:
                logger.debug(f"⚡ Cache hit (Local): {key}")
                return value
            else:
                del _cache_store[key]
                logger.debug(f"🕒 Cache expired (Local): {key}")
    return None


def cache_set(key: str, value: Any, expire_seconds: int = 3600) -> bool:
    """Set cache value with TTL (in seconds)."""
    try:
        if USE_REDIS and r:
            r.setex(key, expire_seconds, safe_json_dumps(value))
            logger.debug(f"💾 Cache set (Redis): {key} ({expire_seconds}s)")
        else:
            with _cache_lock:
                expire_time = datetime.now() + timedelta(seconds=expire_seconds)
                _cache_store[key] = (value, expire_time)
                logger.debug(f"💾 Cache set (Local): {key} ({expire_seconds}s)")
        return True
    except Exception as e:
        logger.warning(f"Cache set error for {key}: {e}")
        return False


def cache_delete(key: str) -> None:
    """Delete a single cache key."""
    try:
        if USE_REDIS and r:
            r.delete(key)
        else:
            with _cache_lock:
                _cache_store.pop(key, None)
        logger.debug(f"🗑️ Cache deleted: {key}")
    except Exception as e:
        logger.warning(f"Cache delete error for {key}: {e}")


def clear_cache(prefix: str = "") -> None:
    """Clear all cache keys matching a prefix."""
    try:
        if USE_REDIS and r:
            cursor = "0"
            while cursor != 0:
                cursor, keys = r.scan(cursor=cursor, match=f"{prefix}*", count=100)
                if keys:
                    r.delete(*keys)
        else:
            with _cache_lock:
                for k in list(_cache_store.keys()):
                    if k.startswith(prefix):
                        del _cache_store[k]
        logger.info(f"🧹 Cleared cache for prefix '{prefix}'")
    except Exception as e:
        logger.error(f"Cache clear error for {prefix}: {e}")


# =========================================================
# 🎯 Convenience Wrappers
# =========================================================
def cache_claim_score(claimant_id: str, data: Dict[str, Any]) -> None:
    """Cache fraud detection result for claimant."""
    cache_set(f"fraud:score:{claimant_id}", data, expire_seconds=1800)


def get_cached_claim_score(claimant_id: str) -> Optional[Dict[str, Any]]:
    """Get cached fraud score."""
    return cache_get(f"fraud:score:{claimant_id}")


def cache_api_response(api_name: str, query: str, data: Dict[str, Any], ttl: int = 3600) -> None:
    """Cache external API response (weather, vendor, etc.)"""
    cache_set(f"api:{api_name}:{query}", data, ttl)


def get_cached_api_response(api_name: str, query: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached API response."""
    return cache_get(f"api:{api_name}:{query}")


# =========================================================
# 🧪 Manual Test
# =========================================================
if __name__ == "__main__":
    print("Testing cache layer...")
    cache_set("test:key", {"message": "Hello Cache!"}, 5)
    print("GET:", cache_get("test:key"))
    cache_delete("test:key")
    print("GET after delete:", cache_get("test:key"))
