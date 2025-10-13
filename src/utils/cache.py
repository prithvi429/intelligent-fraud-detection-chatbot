"""
Cache Utility
-------------
Handles Redis + in-memory fallback for caching fraud scores, NLP results, and external API responses.
Optimized for FastAPI async workloads and safe in local/AWS setups.
"""

import json
import threading
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
from src.config import config
from src.utils.logger import logger

try:
    import redis
except ImportError:
    redis = None

# =========================================================
# 🧠 In-memory fallback
# =========================================================
_cache_store: Dict[str, Any] = {}
_cache_lock = threading.Lock()


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
# 🧩 Core Cache Functions (module-level helpers)
# =========================================================
def cache_get(key: str) -> Optional[Any]:
    """Get cached value by key from local in-memory store."""
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
    """Set cache value with TTL (in seconds) in the local in-memory store."""
    try:
        with _cache_lock:
            expire_time = datetime.now() + timedelta(seconds=expire_seconds)
            _cache_store[key] = (value, expire_time)
            logger.debug(f"💾 Cache set (Local): {key} ({expire_seconds}s)")
        return True
    except Exception as e:
        logger.warning(f"Cache set error for {key}: {e}")
        return False


def cache_delete(key: str) -> None:
    """Delete a single cache key from the local store."""
    try:
        with _cache_lock:
            _cache_store.pop(key, None)
        logger.debug(f"🗑️ Cache deleted: {key}")
    except Exception as e:
        logger.warning(f"Cache delete error for {key}: {e}")


def clear_cache(prefix: str = "") -> None:
    """Clear all cache keys matching a prefix from local store."""
    try:
        with _cache_lock:
            for k in list(_cache_store.keys()):
                if k.startswith(prefix):
                    del _cache_store[k]
        logger.info(f"🧹 Cleared cache for prefix '{prefix}'")
    except Exception as e:
        logger.error(f"Cache clear error for {prefix}: {e}")


# =========================================================
# 🧩 RedisCache class (exported for tests)
# =========================================================
class RedisCache:
    """Cache manager exposing a Redis-backed interface with in-memory fallback."""

    def __init__(self, url: Optional[str] = None):
        self.url = url or getattr(config, "REDIS_URL", "redis://localhost:6379/0")
        self._local_cache = _cache_store
        self._lock = _cache_lock
        self.client = None
        self.use_redis = False

        if redis is None:
            logger.warning("⚠️ redis package not installed — using local in-memory cache.")
            return

        try:
            self.client = redis.from_url(self.url, decode_responses=True, socket_timeout=3)
            self.client.ping()
            self.use_redis = True
            logger.info(f"✅ Connected to Redis at {self.url}")
        except Exception as e:
            self.client = None
            self.use_redis = False
            logger.warning(f"⚠️ Redis unavailable ({e}). Using local in-memory cache instead.")

    def get_client(self):
        return self.client

    def set(self, key: str, value: Any, expire: int = 3600):
        try:
            if self.use_redis and self.client:
                self.client.setex(key, expire, safe_json_dumps(value))
                logger.debug(f"💾 Cache set (Redis): {key} ({expire}s)")
            else:
                with self._lock:
                    expire_time = datetime.now() + timedelta(seconds=expire)
                    self._local_cache[key] = (value, expire_time)
                    logger.debug(f"💾 Cache set (Local): {key} ({expire}s)")
        except Exception as e:
            logger.warning(f"Cache set error for {key}: {e}")

    def get(self, key: str) -> Optional[Any]:
        try:
            if self.use_redis and self.client:
                value = self.client.get(key)
                return json.loads(value) if value else None

            with self._lock:
                entry = self._local_cache.get(key)
                if entry:
                    value, expire_time = entry
                    if datetime.now() < expire_time:
                        logger.debug(f"⚡ Cache hit (Local): {key}")
                        return value
                    else:
                        del self._local_cache[key]
                        logger.debug(f"🕒 Cache expired (Local): {key}")
            return None
        except Exception as e:
            logger.debug(f"Cache get failed for {key}: {e}")
            return None

    def delete(self, key: str) -> None:
        try:
            if self.use_redis and self.client:
                self.client.delete(key)
            else:
                with self._lock:
                    self._local_cache.pop(key, None)
            logger.debug(f"🗑️ Cache deleted: {key}")
        except Exception as e:
            logger.warning(f"Cache delete error for {key}: {e}")

    def clear(self, prefix: str = "") -> None:
        try:
            if self.use_redis and self.client:
                cursor = 0
                while True:
                    cursor, keys = self.client.scan(cursor=cursor, match=f"{prefix}*", count=100)
                    if keys:
                        self.client.delete(*keys)
                    if cursor == 0:
                        break
            else:
                with self._lock:
                    for k in list(self._local_cache.keys()):
                        if k.startswith(prefix):
                            del self._local_cache[k]
            logger.info(f"🧹 Cleared cache for prefix '{prefix}'")
        except Exception as e:
            logger.error(f"Cache clear error for {prefix}: {e}")


__all__ = [
    "RedisCache",
    "cache_get",
    "cache_set",
    "cache_delete",
    "clear_cache",
]
