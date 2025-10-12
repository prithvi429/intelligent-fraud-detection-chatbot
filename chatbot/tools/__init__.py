"""
Chatbot Tools
-------------
LangChain-compatible tools for the agent:
- submit_and_score: Analyze claims via backend API.
- explain_alarms: Explain fraud alarms.
- retrieve_guidance: Retrieve policy guidance (RAG).
- qa_handler: Handle rejection or "why" questions.
"""

from langchain.tools import tool
from importlib import import_module

TOOL_MODULES = [
    "chatbot.tools.submit_and_score",
    "chatbot.tools.explain_alarms",
    "chatbot.tools.retrieve_guidance",
    "chatbot.tools.qa_handler",
]

__all__ = ["submit_and_score", "explain_alarms", "retrieve_guidance", "qa_handler"]

# Dynamically import all tools
for module in TOOL_MODULES:
    import_module(module)
