"""
AWS Lambda Handler for Chatbot
------------------------------
Serverless entry point for the Fraud Detection Chatbot.

Purpose:
    - Handles AWS API Gateway requests (POST /guidance or full agent)
    - Runs the chatbot agent (LLM + RAG + Tools)
    - Returns structured JSON responses

Expected Event:
    {
        "query": "User input text",
        "session_id": "optional"
    }

Response:
    {
        "response": "Chatbot reply",
        "session_id": "lambda_session"
    }

Deploy:
    - Use `requirements_lambda.txt` (lightweight build)
    - Exclude heavy LangChain modules if using partial tool logic
"""

import json
import os
from typing import Any, Dict

from dotenv import load_dotenv

# Local imports
from .agent import run_agent
from .utils.logger import logger

# Load environment variables for local testing
load_dotenv()


# =========================================================
# ⚙️ Warm-Start Optimization (Cold Start Mitigation)
# =========================================================
# AWS Lambda reuses execution context between invocations.
# This loads the model once and caches the agent for faster response.
CACHED_AGENT = None


def get_cached_agent():
    """Lazy load agent instance once (reused across invocations)."""
    global CACHED_AGENT
    if CACHED_AGENT is None:
        try:
            from .agent import create_agent
            CACHED_AGENT, _ = create_agent(session_id="lambda_boot")
            logger.info("✅ Chatbot agent cached for warm starts.")
        except Exception as e:
            logger.error(f"Failed to preload agent: {e}")
    return CACHED_AGENT


# =========================================================
# 🧠 Lambda Handler
# =========================================================
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entry function.

    Args:
        event: AWS event (usually from API Gateway)
        context: Lambda runtime context
    Returns:
        dict: API Gateway-compatible JSON response
    """
    try:
        # Parse request body
        body_raw = event.get("body", "{}")
        body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw

        query = body.get("query")
        session_id = body.get("session_id", "lambda_session")

        if not query:
            return {
                "statusCode": 400,
                "headers": _cors_headers(),
                "body": json.dumps({"error": "Missing 'query' in request body"})
            }

        # ✅ Use cached agent (warm start) or fallback to fresh run
        agent = get_cached_agent()
        if agent:
            logger.info("🔁 Using cached agent instance.")
            response = agent.invoke({"input": query}).get("output", "")
        else:
            response = run_agent(query, session_id)

        logger.info(f"Lambda Query: {query[:60]} → Response: {response[:60]}")

        return {
            "statusCode": 200,
            "headers": _cors_headers(),
            "body": json.dumps({
                "response": response,
                "session_id": session_id
            })
        }

    except Exception as e:
        logger.error(f"❌ Lambda runtime error: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": _cors_headers(),
            "body": json.dumps({"error": "Internal server error"})
        }


# =========================================================
# 🌍 Helpers
# =========================================================
def _cors_headers() -> Dict[str, str]:
    """Reusable CORS headers."""
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "OPTIONS,POST",
        "Access-Control-Allow-Headers": "Content-Type,Authorization"
    }


# =========================================================
# 🧪 Local Test (Standalone)
# =========================================================
if __name__ == "__main__":
    test_event = {"body": json.dumps({"query": "List fraud detection documents"})}
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
