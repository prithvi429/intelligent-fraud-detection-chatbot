Chatbot module

This package contains the agent, tools, prompts and utilities used by the conversational assistant that explains claim decisions and assists claimants.

Structure:
- agent.py: orchestrates tool calls and LLM prompts
- tools/: small wrappers to call backend APIs and fetch guidance
- prompts/: system and user prompt templates
- utils/: session manager and formatting helpers

Run tests with `pytest chatbot/tests`.
