"""
Chat Logger
-----------
Structured JSON logging for chatbot interactions.
- Works in both local (stdout) and production (CloudWatch/ELK) environments.
- Logs query events, tool calls, responses, and errors with metadata.
- Uses global logger if available, or standalone JSON logger otherwise.

Usage:
    chat_logger.info("Query processed")
    log_query("session_123", "User asked about claim refund")
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# -------------------------------------------------------------
# 🌍 Use global app logger if available
# -------------------------------------------------------------
try:
    from src.utils.logger import logger as global_logger
except ImportError:
    global_logger = None

# -------------------------------------------------------------
# 🧩 Chatbot-specific logger (inherits from global)
# -------------------------------------------------------------
chat_logger = logging.getLogger("chatbot")
chat_logger.setLevel(logging.INFO)

# -------------------------------------------------------------
# 🧱 Safe JSON Logging Helper
# -------------------------------------------------------------
def log_event(
    event_type: str,
    message: str,
    extra: Optional[Dict[str, Any]] = None,
    level: str = "INFO",
) -> None:
    """
    Emit structured JSON logs for chatbot events.
    Args:
        event_type: Identifier for event ("query_received", "tool_called", etc.)
        message: Readable log message.
        extra: Additional structured data.
        level: "INFO", "WARNING", or "ERROR".
    """
    try:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "logger": "chatbot",
            "event_type": event_type,
            "message": message,
            "session_id": extra.get("session_id") if extra else None,
            "user_id": extra.get("user_id") if extra else None,
            "extra": extra or {},
        }

        # Choose log method
        log_method = getattr(chat_logger, level.lower(), chat_logger.info)

        # Safe JSON dump
        try:
            formatted = json.dumps(log_entry, default=str)
        except Exception:
            formatted = str(log_entry)

        # Emit log
        log_method(formatted)

        # Forward to global logger if configured
        if global_logger:
            global_logger.log(getattr(logging, level.upper(), logging.INFO), formatted)

        # Flush immediately (important for AWS Lambda)
        for handler in chat_logger.handlers:
            if hasattr(handler, "flush"):
                handler.flush()

    except Exception as e:
        # Prevent log failures from crashing the app
        print(f"[ChatLogger Error] {type(e).__name__}: {e}")


# -------------------------------------------------------------
# 🚀 Convenience Logging Functions
# -------------------------------------------------------------
def log_query(session_id: str, query: str, user_id: str = "anonymous") -> None:
    """Log incoming query from a user."""
    log_event(
        "query_received",
        f"User query: {query[:100]}...",
        {"session_id": session_id, "query": query, "user_id": user_id},
    )


def log_tool_call(session_id: str, tool_name: str, input_data: Dict[str, Any]) -> None:
    """Log a tool invocation (LangChain or backend API)."""
    log_event(
        "tool_called",
        f"Tool called: {tool_name}",
        {"session_id": session_id, "tool_name": tool_name, "input": input_data},
    )


def log_response(session_id: str, response: str, tokens_used: int = 0) -> None:
    """Log AI response event."""
    log_event(
        "response_generated",
        f"Response generated ({tokens_used} tokens)",
        {
            "session_id": session_id,
            "response_preview": response[:120],
            "tokens_used": tokens_used,
        },
    )


def log_error(session_id: str, error: str, query: Optional[str] = None) -> None:
    """Log chatbot or tool error."""
    extra = {"session_id": session_id, "error": error}
    if query:
        extra["query"] = query
    log_event("chat_error", f"Error in chatbot: {error}", extra, "ERROR")


# -------------------------------------------------------------
# ⚙️ Logger Initialization
# -------------------------------------------------------------
def setup_chat_logger() -> None:
    """
    Configure logger handlers & formatters.
    Ensures clean JSON logging even if global logger isn't configured.
    """
    if not chat_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(message)s")  # Emit JSON as-is
        handler.setFormatter(formatter)
        chat_logger.addHandler(handler)
        chat_logger.propagate = False
        chat_logger.info(json.dumps({
            "event_type": "logger_init",
            "message": "Chat logger initialized successfully.",
            "timestamp": datetime.utcnow().isoformat()
        }))


# Initialize on import
setup_chat_logger()
