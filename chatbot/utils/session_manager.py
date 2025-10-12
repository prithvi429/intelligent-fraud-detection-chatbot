"""
Session Manager
---------------
Manages conversation history across chat sessions.

Features:
- Tracks message history (role, content, timestamp)
- Counts tokens (tiktoken) to stay within model context
- Supports persistence via Redis (optional)
- Automatically prunes oldest messages when exceeding max tokens

Usage:
    session = SessionManager("session_123")
    session.add_message("human", "Hello!")
    print(session.get_history())
"""

import json
import redis
import tiktoken
from datetime import datetime
from typing import List, Dict, Optional
from ..config.settings import settings
from ..utils.logger import chat_logger


class SessionManager:
    """
    Manage a chat session for a user or conversation.
    Supports in-memory and Redis-based storage.

    Args:
        session_id (str): Unique identifier (UUID, user ID, etc.)
        use_redis (bool): Enable Redis persistence (default: False)
    """
    def __init__(self, session_id: str, use_redis: bool = False):
        self.session_id = session_id
        self.messages: List[Dict[str, str]] = []
        self._token_count = 0

        # Redis setup (optional)
        self.use_redis = use_redis and bool(settings.REDIS_URL)
        self.redis_client: Optional[redis.Redis] = None

        if self.use_redis:
            try:
                self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            except Exception as e:
                chat_logger.warning(f"⚠️ Redis connection failed — falling back to in-memory. Error: {e}")
                self.use_redis = False

        self._load_history()

    # --------------------------------------------------------
    # 🧠 Token Counting
    # --------------------------------------------------------
    def _get_encoding(self) -> tiktoken.Encoding:
        """Return GPT model tokenizer."""
        return tiktoken.encoding_for_model("gpt-3.5-turbo")

    def _count_tokens(self, text: str) -> int:
        """Estimate token count for given text."""
        if not text:
            return 0
        try:
            return len(self._get_encoding().encode(text))
        except Exception:
            return len(text.split())  # fallback

    # --------------------------------------------------------
    # 💬 Message Management
    # --------------------------------------------------------
    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to session history and update token count.
        Args:
            role: "human" or "ai"
            content: Message text
        """
        if role not in {"human", "ai"}:
            raise ValueError("Role must be 'human' or 'ai'")

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }

        self.messages.append(message)
        tokens = self._count_tokens(content)
        self._token_count += tokens

        # Enforce token budget
        max_tokens = getattr(settings, "MAX_TOKENS", 4000)
        while self._token_count > max_tokens and len(self.messages) > 1:
            removed = self.messages.pop(0)
            self._token_count -= self._count_tokens(removed["content"])

        # Persist if Redis enabled
        if self.use_redis:
            self._save_history()

    def get_history(self, max_messages: Optional[int] = None) -> List[Dict]:
        """Return session messages (latest first)."""
        if max_messages:
            return self.messages[-max_messages:]
        return self.messages

    def get_token_count(self) -> int:
        """Return total token count."""
        return self._token_count

    def clear(self) -> None:
        """Wipe session history."""
        self.messages.clear()
        self._token_count = 0
        if self.use_redis and self.redis_client:
            self.redis_client.delete(self._redis_key())

    # --------------------------------------------------------
    # 💾 Redis Persistence
    # --------------------------------------------------------
    def _redis_key(self) -> str:
        """Redis key for session data."""
        return f"session:{self.session_id}"

    def _save_history(self) -> None:
        """Persist chat history to Redis."""
        if not (self.use_redis and self.redis_client):
            return
        try:
            self.redis_client.set(
                self._redis_key(),
                json.dumps(self.messages),
                ex=3600  # TTL = 1 hour
            )
        except Exception as e:
            chat_logger.warning(f"⚠️ Redis save failed: {e}")

    def _load_history(self) -> None:
        """Load chat history from Redis."""
        if not (self.use_redis and self.redis_client):
            return
        try:
            data = self.redis_client.get(self._redis_key())
            if data:
                self.messages = json.loads(data)
                self._token_count = sum(self._count_tokens(msg["content"]) for msg in self.messages)
                chat_logger.info(f"📦 Restored session: {self.session_id} ({len(self.messages)} messages)")
        except Exception as e:
            chat_logger.warning(f"⚠️ Redis load failed: {e}")

# --------------------------------------------------------
# 🧩 Factory Helper
# --------------------------------------------------------
def get_session(session_id: str) -> SessionManager:
    """Return a session instance with correct Redis config."""
    return SessionManager(session_id, use_redis=getattr(settings, "USE_REDIS_SESSIONS", False))
