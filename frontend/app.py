"""
Fraud Detection Chatbot Frontend
--------------------------------
Streamlit app providing two main features:
1. 💬 Chatbot Mode — Ask policy or claim questions (uses /guidance API).
2. 📄 Claim Analysis Mode — Submit or upload claim for fraud detection (/score_claim API).

Usage:
    streamlit run app.py
"""

import os
import re
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", 20))

# Internal imports
from utils.api_client import call_score_claim, call_guidance
from utils.session_state import get_session_id, add_message
from utils.formatter import format_fraud_response, format_guidance_response
from components.chat_interface import display_chat_history
from components.claim_form import claim_input_form
from components.result_panel import display_results
from components.fraud_visualizer import show_fraud_viz

# ------------------------------------------------------------
# 🧭 Streamlit Page Configuration
# ------------------------------------------------------------
st.set_page_config(
    page_title="🛡️ Insurance Fraud Detection Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load custom CSS (optional)
if os.path.exists("static/style.css"):
    with open("static/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ------------------------------------------------------------
# 🏷️ Title & Sidebar
# ------------------------------------------------------------
st.title("🛡️ Insurance Fraud Detection Assistant")
st.markdown("Chat naturally or submit a claim for fraud analysis and policy guidance.")

page = st.sidebar.selectbox("Choose Mode", ["💬 Chat Assistant", "📄 Claim Analysis"])

# ------------------------------------------------------------
# 💾 Session Initialization
# ------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = get_session_id()

# ------------------------------------------------------------
# 💬 Chat Assistant Mode
# ------------------------------------------------------------
def render_chat_mode():
    st.header("💬 Chat with FraudBot")

    # Show chat history (limit)
    display_chat_history(st.session_state.messages[-MAX_HISTORY:])

    # Chat input box
    user_input = st.chat_input("Ask about claims, fraud policies, or upload guidance...")

    if user_input:
        add_message(st.session_state, "user", user_input)
        with st.chat_message("user"):
            st.markdown(user_input)

        # Process and display bot response
        with st.chat_message("assistant"):
            with st.spinner("Thinking... 🤔"):
                try:
                    response = process_chat_input(user_input, st.session_state.session_id)
                    formatted = format_chat_response(response)

                    st.markdown(formatted["text"])

                    if "fraud_data" in formatted:
                        show_fraud_viz(formatted["fraud_data"])
                    if "guidance_data" in formatted:
                        display_results(formatted["guidance_data"])

                    add_message(st.session_state, "assistant", formatted["text"])

                except Exception as e:
                    st.error(f"⚠️ Chatbot error: {e}")

# ------------------------------------------------------------
# 📄 Claim Analysis Mode
# ------------------------------------------------------------
def render_claim_mode():
    st.header("📄 Submit a Claim for Analysis")

    claim_data = claim_input_form()

    if st.button("🔍 Analyze Claim", type="primary"):
        if not claim_data:
            st.warning("Please fill in claim details or upload a file.")
            return

        with st.spinner("Analyzing claim..."):
            try:
                response = call_score_claim(claim_data, BACKEND_URL)
                if not response:
                    st.error("❌ Backend did not return a valid response.")
                    return

                formatted = format_fraud_response(response)
                display_results(formatted)
                show_fraud_viz(formatted)

            except Exception as e:
                st.error(f"⚠️ Error contacting backend: {e}")

# ------------------------------------------------------------
# 🧠 Core Logic
# ------------------------------------------------------------
def process_chat_input(prompt: str, session_id: str) -> dict:
    """Detects claim-like vs policy question → routes to appropriate API."""
    claim_keywords = ["claim", "amount", "$", "accident", "injury", "provider", "hospital"]
    if any(word in prompt.lower() for word in claim_keywords):
        claim_data = {
            "amount": extract_amount(prompt) or 5000.0,
            "report_delay_days": extract_delay(prompt) or 0,
            "notes": prompt,
            "claimant_id": f"{session_id}_{datetime.now().timestamp()}",
            "provider": extract_provider(prompt) or "Unknown",
            "location": extract_location(prompt) or "Unknown",
            "is_new_bank": "new bank" in prompt.lower(),
        }
        return call_score_claim(claim_data, BACKEND_URL)
    else:
        return call_guidance(prompt, BACKEND_URL)

def format_chat_response(response: dict) -> dict:
    """Format chatbot or fraud result for display."""
    if not response:
        return {"text": "⚠️ No response received. Please try again."}

    if "fraud_probability" in response:
        return format_fraud_response(response)
    elif "guidance" in response or "response" in response:
        return {"text": format_guidance_response(response), "guidance_data": response}
    else:
        return {"text": "🤔 Sorry, I couldn’t understand that. Try rephrasing your question."}

# ------------------------------------------------------------
# 🔎 Helper Extractors (Regex-based)
# ------------------------------------------------------------
def extract_amount(text: str) -> float | None:
    match = re.search(r"\$?(\d+(?:,\d{3})*(?:\.\d{2})?)", text)
    return float(match.group(1).replace(",", "")) if match else None

def extract_delay(text: str) -> int | None:
    match = re.search(r"(?:delay|reported)\s*(\d+)", text, re.I)
    return int(match.group(1)) if match else None

def extract_provider(text: str) -> str | None:
    match = re.search(r"(?:provider|clinic|hospital)\s*([A-Za-z\s]+)", text, re.I)
    return match.group(1).strip() if match else None

def extract_location(text: str) -> str | None:
    match = re.search(r"(?:location|city)\s*([A-Za-z\s,]+)", text, re.I)
    return match.group(1).strip() if match else None

# ------------------------------------------------------------
# 🚀 App Entry Point
# ------------------------------------------------------------
def main():
    if page.startswith("💬"):
        render_chat_mode()
    else:
        render_claim_mode()

    # Footer
    st.markdown("---")
    st.caption("⚙️ Backend: FastAPI + AWS SageMaker • © 2025 FraudBot")

if __name__ == "__main__":
    main()
