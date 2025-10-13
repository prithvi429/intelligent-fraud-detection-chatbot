"""
Guidance Service
----------------
Provides FAQ and general guidance for claim-related queries.
"""

def get_guidance_response(query: str) -> dict:
    """Returns a simple mock guidance response."""
    query = query.lower().strip()
    if "document" in query:
        return {"response": "You need to submit ID proof, medical bills, and police report if applicable."}
    elif "status" in query:
        return {"response": "You can track your claim status on the portal using your claim ID."}
    else:
        return {"response": "Please rephrase your question or contact support for help."}
