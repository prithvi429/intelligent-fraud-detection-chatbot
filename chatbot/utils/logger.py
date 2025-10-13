"""
Logger Utility
--------------
Centralized logging helper for the chatbot system.

- Provides consistent JSON-style log format.
- Falls back to Python's built-in logging if backend logger unavailable.
- Used across tools (submit_and_score, explain_alarms, etc.) for traceability.

Usage:
    from chatbot.utils.logger import log_tool_call, logger
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# =========================================================
# 🪵 Attempt to import shared backend logger (if available)
# =========================================================
try:
    # If running in same environment as backend service
    from src.utils.logger import logger as global_logger
except Exception:
    # Fallback: local logger setup
    global_logger = logging.getLogger("fraudbot")
    if not global_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        global_logger.addHandler(handler)
        global_logger.setLevel(logging.INFO)


# =========================================================
# 📘 Log tool invocation for traceability
# =========================================================
def log_tool_call(
    session_id: str,
    tool_name: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log every LangChain tool invocation for observability.

    Args:
        session_id (str): Active chat session identifier.
        tool_name (str): Tool being used (e.g., submit_and_score, explain_alarms).
        metadata (dict, optional): Additional structured info.
    """
    log_entry = {
        "event": "tool_invocation",
        "timestamp": datetime.utcnow().isoformat(),
        "session_id": session_id,
        "tool": tool_name,
        "metadata": metadata or {},
    }

    try:
        global_logger.info(json.dumps(log_entry, ensure_ascii=False))
    except Exception as e:
        print(f"[LOGGING ERROR] {e}: {log_entry}")


# =========================================================
# ❌ Log errors in a standardized way
# =========================================================
def log_error(context: str, error: Exception, details: Optional[str] = None):
    """
    Log system or runtime errors in structured form.

    Args:
        context (str): Module or function where the error occurred.
        error (Exception): The raised exception.
        details (str, optional): Additional context or input.
    """
    log_entry = {
        "event": "error",
        "timestamp": datetime.utcnow().isoformat(),
        "context": context,
        "error_type": type(error).__name__,
        "message": str(error),
        "details": details or "",
    }

    try:
        global_logger.error(json.dumps(log_entry, ensure_ascii=False))
    except Exception as e:
        print(f"[LOGGING ERROR] {e}: {log_entry}")


# =========================================================
# 🔧 Public logger object (for direct use)
# =========================================================
logger = global_logger

# ✅ Backward compatibility alias (for old imports)
chat_logger = logger


# =========================================================
# 🚀 Startup message helper
# =========================================================
def log_startup():
    """Log startup banner and environment."""
    logger.info("🚀 Fraud Detection Chatbot initialized successfully.")


# Example usage:
# logger.info("Chatbot initialized")
# log_tool_call("session_123", "submit_and_score", {"query": "Score claim"})
