"""
RedisCache Utility
------------------
Provides caching via Redis with safe in-memory fallback.
"""

import json

try:
    import redis
except ImportError:
    redis = None


class RedisCache:
    """Cache manager with Redis + in-memory fallback."""

    _local_cache = {}

    def __init__(self, url: str = "redis://localhost:6379/0"):
        self.url = url
        self.client = self._connect()

    def _log(self, level: str, message: str):
        """Local import avoids circular dependencies with logger."""
        try:
            from src.utils.logger import logger
            getattr(logger, level, logger.info)(message)
        except Exception:
            print(f"[Cache-{level.upper()}] {message}")

    def _connect(self):
        """Try connecting to Redis, fallback if fails."""
        if not redis:
            self._log("warning", "⚠️ Redis not installed — using local in-memory cache.")
            return None
        try:
            client = redis.StrictRedis.from_url(self.url, decode_responses=True)
            client.ping()
            self._log("info", f"✅ Connected to Redis at {self.url}")
            return client
        except Exception as e:
            self._log("warning", f"⚠️ Redis unavailable ({e}). Using in-memory cache instead.")
            return None

    def get_client(self):
        """Return Redis client or None."""
        return self.client

    # ---------------- Core Cache Ops ---------------- #
    def set(self, key: str, value, expire: int = 3600):
        try:
            data = json.dumps(value)
            if self.client:
                self.client.setex(key, expire, data)
            else:
                self._local_cache[key] = value
        except Exception as e:
            self._log("error", f"❌ Failed to set cache for {key}: {e}")

    def get(self, key: str):
        try:
            if self.client:
                data = self.client.get(key)
                return json.loads(data) if data else None
            return self._local_cache.get(key)
        except Exception as e:
            self._log("error", f"❌ Failed to get cache for {key}: {e}")
            return None

    def delete(self, key: str):
        try:
            if self.client:
                self.client.delete(key)
            elif key in self._local_cache:
                del self._local_cache[key]
        except Exception as e:
            self._log("error", f"❌ Failed to delete cache for {key}: {e}")
