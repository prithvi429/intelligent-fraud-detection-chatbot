"""
Retrieve Guidance Tool (RAG)
----------------------------
LangChain tool: Semantic search for insurance policy guidance using Pinecone or backend DB fallback.

Features:
- Semantic RAG: Embeds query → retrieves top-k results from Pinecone
- Fallback: Uses backend /guidance API if Pinecone unavailable or confidence < threshold
- Formatting: Clean Markdown (response, documents, confidence, source)
- Logging: Tracks tool calls and errors for observability

Usage:
    retrieve_guidance("What documents are required for filing a claim?", session_id="sess_123")
"""

from langchain.tools import tool
from langchain_openai import OpenAIEmbeddings
from typing import Optional
import pinecone

from ..utils.api_client import call_guidance
from ..utils.logger import log_tool_call, log_error
from ..config.settings import settings
from ..config.constants import GUIDANCE_THRESHOLD


@tool("retrieve_guidance", return_direct=True)
def retrieve_guidance(query: str, session_id: Optional[str] = None) -> str:
    """
    Retrieve policy or procedural guidance related to insurance claims.

    Args:
        query (str): User's policy question (e.g., "What documents are needed for a claim?")
        session_id (Optional[str]): Chat session ID for logging.

    Returns:
        str: Markdown-formatted policy response with required documents and confidence score.
    """
    session_id = session_id or "anonymous"
    log_tool_call(session_id, "retrieve_guidance", {"query": query[:100]})

    try:
        # ------------------------------------------------
        # 🧠 Step 1: Semantic Retrieval (Pinecone)
        # ------------------------------------------------
        if settings.PINECONE_ENABLED:
            pinecone.init(api_key=settings.PINECONE_API_KEY, environment=settings.PINECONE_ENV)
            index = pinecone.Index(settings.PINECONE_INDEX_NAME)

            embeddings = OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)
            query_embedding = embeddings.embed_query(query)

            results = index.query(vector=query_embedding, top_k=3, include_metadata=True)

            if not results.matches:
                return _fallback_to_db(query, session_id)

            top_match = results.matches[0]
            score = top_match.score or 0.0

            # Low-confidence → fallback
            if score < GUIDANCE_THRESHOLD:
                return _fallback_to_db(query, session_id)

            metadata = top_match.metadata or {}
            response = metadata.get("response", "No relevant guidance found.")
            docs = metadata.get("required_docs", [])
            source = metadata.get("source", "Policy Knowledge Base")

            # Format final Markdown
            formatted = [
                f"📖 **Guidance for:** '{query.strip()[:60]}...'",
                "",
                response.strip(),
                "",
            ]

            if docs:
                formatted.append("**📋 Required Documents / Steps:**")
                for doc in docs:
                    formatted.append(f"• {doc}")
                formatted.append("")

            formatted.append(f"**Source:** {source}  |  **Confidence:** {score:.1%}")
            formatted.append(
                "\n💡 *Tip:* If this doesn’t fully answer your question, try being more specific (e.g., 'What docs for accident claim?')."
            )

            return "\n".join(formatted)

        # ------------------------------------------------
        # 🧩 Step 2: Fallback (DB or API)
        # ------------------------------------------------
        return _fallback_to_db(query, session_id)

    except Exception as e:
        log_error(session_id, f"Guidance retrieval failed: {e}", query)
        return (
            "❌ **System Error:** Unable to fetch guidance right now.\n"
            "Please try again later or rephrase your question."
        )


# ------------------------------------------------------------
# 🔁 Fallback Function: Backend API (/guidance)
# ------------------------------------------------------------
def _fallback_to_db(query: str, session_id: Optional[str] = None) -> str:
    """Fallback method: Uses backend API when Pinecone is disabled or returns low-confidence."""
    try:
        result = call_guidance(query, settings.BACKEND_URL)
        if not result:
            return (
                "⚠️ **No matching guidance found.**\n"
                "Common policy note: You typically need ID, invoice, and claim form. For appeals, contact support within 30 days."
            )

        guidance = result.get("guidance", {})
        response = guidance.get("response", "No detailed response available.")
        docs = guidance.get("required_docs", [])
        score = result.get("relevance_score", 0.0)

        formatted = [
            "📘 **Policy Guidance (from Database)**",
            "",
            response.strip(),
            "",
        ]

        if docs:
            formatted.append("**📋 Required Documents / Steps:**")
            for doc in docs:
                formatted.append(f"• {doc}")
            formatted.append("")

        formatted.append(f"**Match Confidence:** {score:.1%}")
        formatted.append(
            "\n💡 *Tip:* Ask follow-ups like “Why was my claim rejected?” or “How to appeal a decision?”"
        )

        return "\n".join(formatted)

    except Exception as e:
        log_error(session_id or "anonymous", f"Fallback guidance failed: {e}", query)
        return "⚠️ **Error:** Could not retrieve guidance at the moment. Please try again later."
