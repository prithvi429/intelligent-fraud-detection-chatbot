"""
Fraud Visualizer Component
--------------------------
Displays fraud probability (pie/progress), alarms, and decision badges.

Usage:
    show_fraud_viz({
        "probability": 75,
        "decision": "Reject",
        "alarms": [{"type": "blacklist_hit", "description": "Provider in blacklist", "severity": "high"}],
        "explanation": "High-risk due to multiple critical fraud indicators."
    })
"""

import streamlit as st
import plotly.graph_objects as go


def show_fraud_viz(data: dict) -> None:
    """
    Display fraud probability pie chart, decision badge, and alarms.

    Args:
        data (dict): Fraud analysis output containing keys:
            - probability (float)
            - decision (str)
            - alarms (list[dict])
            - explanation (str)
    """
    if not data:
        st.warning("⚠️ No fraud data available for visualization.")
        return

    prob = data.get("probability", 0)
    decision = data.get("decision", "Review")
    alarms = data.get("alarms", [])
    explanation = data.get("explanation", "")

    # -------------------------------------------------------------------
    # 🎯 Fraud Probability Pie Chart
    # -------------------------------------------------------------------
    st.subheader("📊 Fraud Probability")
    fig = go.Figure(
        data=[
            go.Pie(
                labels=["Fraud Risk", "Legitimate"],
                values=[prob, 100 - prob],
                hole=0.5,
                marker_colors=["#e53935", "#4caf50"],
                textinfo="label+percent",
                textfont_size=14,
            )
        ]
    )
    fig.update_layout(
        showlegend=True,
        margin=dict(l=0, r=0, t=30, b=0),
        height=300,
        title_x=0.5,
        title_font=dict(size=16, color="#333"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # -------------------------------------------------------------------
    # 🏷️ Decision Badge
    # -------------------------------------------------------------------
    decision_color = {
        "approve": "#4caf50",
        "review": "#fb8c00",
        "reject": "#f44336",
    }.get(decision.lower(), "#9e9e9e")

    st.markdown(
        f"""
        <div style="
            display:inline-block;
            background-color:{decision_color};
            color:white;
            padding:6px 14px;
            border-radius:8px;
            font-weight:600;
            font-size:14px;
        ">
            Decision: {decision}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -------------------------------------------------------------------
    # 🚨 Alarms Section
    # -------------------------------------------------------------------
    st.subheader("🚨 Detected Alarms")

    if alarms:
        for alarm in alarms:
            severity = alarm.get("severity", "medium").lower()
            a_type = alarm.get("type", "Unknown").replace("_", " ").title()
            description = alarm.get("description", "No description")

            color = "#f44336" if severity == "high" else "#ffb300" if severity == "medium" else "#43a047"
            icon = "⚠️" if severity == "high" else "🟠" if severity == "medium" else "🟢"

            st.markdown(
                f"""
                <div style="
                    display:flex;
                    align-items:center;
                    margin-bottom:6px;
                    background-color:rgba(0,0,0,0.02);
                    border-left:4px solid {color};
                    padding:6px 10px;
                    border-radius:5px;
                ">
                    <span style="font-size:18px;margin-right:8px;">{icon}</span>
                    <b>{a_type}</b>: {description}
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.success("✅ No fraud alarms detected — claim looks legitimate!")

    # -------------------------------------------------------------------
    # 🧠 Explanation (Optional)
    # -------------------------------------------------------------------
    if explanation:
        with st.expander("🧩 Explanation (Model Insights)"):
            st.markdown(explanation)
