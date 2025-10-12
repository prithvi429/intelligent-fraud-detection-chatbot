"""
Claim Form Component
--------------------
Provides two modes for claim submission:
1. Manual Entry — User fills out claim details.
2. File Upload — PDF/Image auto-extracted via backend OCR.

Returns:
    dict: Claim data ready for scoring (or None if incomplete).

Dependencies:
    - utils/api_client.call_process_invoice()
"""

import streamlit as st
from utils.api_client import call_process_invoice
import os


def claim_input_form() -> dict | None:
    """Display manual claim entry form or upload option. Returns claim dict or None."""
    from dotenv import load_dotenv
    load_dotenv()
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

    st.subheader("📋 Enter Claim Details Manually")

    # ----------------------------------------------------------
    # 🧾 Manual Form
    # ----------------------------------------------------------
    with st.form("claim_form"):
        col1, col2 = st.columns(2)

        with col1:
            amount = st.number_input("Amount ($)", min_value=0.0, value=5000.0, step=100.0)
            delay_days = st.number_input("Report Delay (days)", min_value=0, value=0)
            is_new_bank = st.checkbox("New Bank Account?")

        with col2:
            provider = st.text_input("Provider / Clinic Name")
            location = st.text_input("Claim Location (City, State)")
            notes = st.text_area("Notes / Description", placeholder="Briefly describe the claim...")

        submitted = st.form_submit_button("✅ Submit Manually")

        if submitted:
            if amount <= 0:
                st.error("❌ Amount must be greater than 0.")
                return None

            claim_data = {
                "amount": amount,
                "report_delay_days": delay_days,
                "provider": provider or "Unknown",
                "notes": notes.strip() or "No additional notes provided.",
                "location": location or "Unknown",
                "is_new_bank": is_new_bank,
                "claimant_id": f"form_user_{st.session_state.session_id}",
            }

            st.success("✅ Claim details submitted successfully!")
            return claim_data

    # ----------------------------------------------------------
    # 📤 File Upload Option
    # ----------------------------------------------------------
    st.markdown("---")
    st.subheader("📎 Or Upload Invoice / Claim Document")

    uploaded_file = st.file_uploader(
        "Upload a claim document (PDF, JPG, PNG)",
        type=["pdf", "jpg", "jpeg", "png"],
        help="File will be processed via backend OCR extraction.",
    )

    if uploaded_file:
        st.info("File selected. Click below to process it for OCR extraction.")
        if st.button("🔍 Process Uploaded Document"):
            with st.spinner("Extracting claim details using AI OCR..."):
                try:
                    result = call_process_invoice(uploaded_file, BACKEND_URL)
                    if result and result.get("amount", 0) > 0:
                        st.success("✅ OCR extraction successful! Proceeding with analysis...")
                        return result  # Example: {"amount": 1500, "provider": "ABC Clinic", ...}
                    else:
                        st.warning("⚠️ Could not extract claim details. Please try manual entry.")
                except Exception as e:
                    st.error(f"❌ Upload processing failed: {e}")

    return None
