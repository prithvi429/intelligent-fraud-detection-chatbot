"""
Chatbot Tools Loader
--------------------
Centralized tool imports for LangChain agent.
"""

from importlib import import_module
from chatbot.tools import explain_alarms


TOOL_MODULES = [
    "chatbot.tools.submit_and_score",
    "chatbot.tools.explain_alarms",
    "chatbot.tools.retrieve_guidance",
    "chatbot.tools.qa_handler",
]

__all__ = ["submit_and_score", "explain_alarms", "retrieve_guidance", "qa_handler"]

for module in TOOL_MODULES:
    import_module(module)
