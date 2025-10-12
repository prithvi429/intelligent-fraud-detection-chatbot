"""
Logger Utility
--------------
Centralized logging helper for the chatbot system.

- Provides a consistent JSON-style log format.
- Falls back to Python's built-in logging if backend logger unavailable.
- Used across tools (submit_and_score, explain_alarms, etc.) for traceability.

Usage:
    from chatbot.utils.logger import log_tool_call, logger
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# ---------------------------------------------------------
# 🪵 Try to use shared backend logger if available
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# 📘 Standardized tool call logger
# ---------------------------------------------------------
def log_tool_call(
    session_id: str,
    tool_name: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log every LangChain tool invocation for traceability.

    Args:
        session_id (str): Active chat session identifier.
        tool_name (str): Tool being used (e.g., submit_and_score, explain_alarms).
        metadata (dict, optional): Optional structured data about the call.
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
        # fallback to raw print if logger fails (e.g., during early init)
        print(f"[LOGGING ERROR] {e}: {log_entry}")


# ---------------------------------------------------------
# 🔧 Generic logger wrapper
# ---------------------------------------------------------
logger = global_logger
"""
Alias for consistent import: `from chatbot.utils.logger import logger`
This is the same object used for tool & system logs.
"""

# Example usage:
# logger.info("Chatbot initialized")
# log_tool_call("session_123", "submit_and_score", {"query": "Score claim"})
