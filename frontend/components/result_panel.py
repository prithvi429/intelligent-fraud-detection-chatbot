"""
Result Panel Component
----------------------
Displays formatted results for fraud analysis or policy guidance.

Usage:
    display_results(data: dict)
"""

import streamlit as st


def display_results(data: dict) -> None:
    """Render fraud or guidance results dynamically."""
    if not data:
        st.warning("⚠️ No results to display yet.")
        return

    # --------------------------------------------------------------------
    # 🧠 FRAUD ANALYSIS RESULTS
    # --------------------------------------------------------------------
    if "fraud_probability" in data:
        st.markdown("## 🧠 Fraud Analysis Results")

        prob = data.get("fraud_probability", 0)
        decision = data.get("decision", "Review")
        alarms = data.get("alarms", [])
        explanation = data.get("explanation", "No detailed explanation available.")

        # Decision color coding
        color_map = {
            "approve": "#4caf50",
            "review": "#ffb300",
            "reject": "#f44336",
        }
        decision_color = color_map.get(decision.lower(), "#9e9e9e")

        # Metrics row
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Fraud Probability", f"{prob:.1f}%")
            st.progress(min(prob / 100, 1.0))
        with col2:
            st.markdown(
                f"""
                <div style="
                    padding: 10px 15px;
                    border-radius: 8px;
                    background-color: {decision_color};
                    color: white;
                    font-weight: 600;
                    text-align: center;
                    margin-top: 12px;">
                    Decision: {decision}
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Alarms section
        if alarms:
            st.markdown("### ⚠️ Detected Alarms")
            for alarm in alarms:
                a_type = alarm.get("type", "Unknown").replace("_", " ").title()
                desc = alarm.get("description", "No details.")
                sev = alarm.get("severity", "medium").capitalize()
                icon = "🟥" if sev.lower() == "high" else "🟧" if sev.lower() == "medium" else "🟩"
                st.markdown(f"- {icon} **{a_type}**: {desc}")
        else:
            st.success("✅ No fraud alarms detected.")

        # Explanation collapsible
        with st.expander("🧩 Explanation / Model Insights"):
            st.markdown(explanation)

    # --------------------------------------------------------------------
    # 📖 POLICY GUIDANCE RESULTS
    # --------------------------------------------------------------------
    elif "guidance" in data:
        st.markdown("## 📖 Policy Guidance")

        guidance = data["guidance"]
        response = guidance.get("response", "No response provided.")
        docs = guidance.get("required_docs", [])
        score = data.get("relevance_score", 0)

        # Main answer
        st.info(response)

        # Required documents
        if docs:
            st.markdown("### 📋 Required Documents")
            for doc in docs:
                st.markdown(f"- 🗂️ **{doc}**")

        # Relevance score
        st.caption(f"🔍 Relevance Score: {score:.1%}")

    # --------------------------------------------------------------------
    # Unknown data structure fallback
    # --------------------------------------------------------------------
    else:
        st.error("❌ Unsupported result format. Please verify API response keys.")
