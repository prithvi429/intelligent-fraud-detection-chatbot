"""
Chatbot Config
--------------
Central configuration entry point for the FraudBot system.

Includes:
- settings: Environment-based configuration (API keys, URLs, etc.)
- constants: Fixed configuration values and enums (alarms, emojis, etc.)

Usage:
    from chatbot.config import settings, ALARM_TYPES, MAX_TOKENS
"""

from .settings import settings
from .constants import (
    ALARM_TYPES,
    ALARM_EMOJIS,
    DECISION_EMOJIS,
    MAX_TOKENS,
    GUIDANCE_THRESHOLD,
    SUPPORTED_LANGUAGES,
)

__all__ = [
    "settings",
    "ALARM_TYPES",
    "ALARM_EMOJIS",
    "DECISION_EMOJIS",
    "MAX_TOKENS",
    "GUIDANCE_THRESHOLD",
    "SUPPORTED_LANGUAGES",
]
