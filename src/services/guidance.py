"""
Guidance Service
----------------
Provides chatbot-style guidance responses for user queries.
"""

def get_guidance_response(query: str):
    """Return chatbot-style guidance response and relevance score."""

    if not query.strip():
        # Empty query → low relevance
        return {
            "response": "Please ask a valid question about claims or fraud detection.",
            "relevance_score": 0.0
        }

    # For document-related queries
    if "document" in query.lower():
        return {
            "response": (
                "You need to submit all relevant documents such as ID proof, medical bills, "
                "and a police report if applicable."
            ),
            "relevance_score": 0.95
        }

    # Default fallback for other general questions
    return {
        "response": "I'm here to assist with fraud detection and claim-related queries.",
        "relevance_score": 0.7
    }
