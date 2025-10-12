"""
UI Components Unit Tests
------------------------
Tests Streamlit-based UI components:
- chat_interface
- fraud_visualizer
- claim_form
- result_panel

Mocks Streamlit calls and API dependencies for isolated logic testing.
Run: pytest tests/test_ui_components.py -v
"""

import pytest
from unittest.mock import patch, MagicMock, call, ANY
import streamlit as st

# Import components after mock setup
from frontend.components.chat_interface import display_chat_history
from frontend.components.fraud_visualizer import show_fraud_viz
from frontend.components.claim_form import claim_input_form
from frontend.components.result_panel import display_results
from utils.session_state import get_session_id, add_message, clear_history


# --------------------------------------------------------------------
# 🧠 Shared Streamlit Mock Fixture
# --------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_streamlit():
    """Automatically mock Streamlit calls for all tests."""
    with patch.multiple(
        st,
        markdown=MagicMock(),
        metric=MagicMock(),
        subheader=MagicMock(),
        success=MagicMock(),
        warning=MagicMock(),
        info=MagicMock(),
        error=MagicMock(),
        caption=MagicMock(),
        columns=MagicMock(return_value=[MagicMock(), MagicMock()]),
        expander=MagicMock(return_value=MagicMock()),
        image=MagicMock(),
        plotly_chart=MagicMock(),
        checkbox=MagicMock(return_value=False),
        text_input=MagicMock(return_value=""),
        number_input=MagicMock(return_value=0.0),
        text_area=MagicMock(return_value=""),
        form_submit_button=MagicMock(return_value=False),
        button=MagicMock(return_value=False),
    ):
        yield


# --------------------------------------------------------------------
# 💬 Chat Interface Tests
# --------------------------------------------------------------------
class TestChatInterface:
    def test_display_chat_history_empty(self):
        """Empty history should not render markdown."""
        messages = []
        display_chat_history(messages)
        st.markdown.assert_not_called()

    def test_display_chat_history_user_message(self):
        """User message renders with no special class."""
        messages = [{"role": "user", "content": "Hello"}]
        display_chat_history(messages)
        st.markdown.assert_called_once()
        assert "Hello" in st.markdown.call_args[0][0]

    def test_display_chat_history_high_risk(self):
        """Assistant message with 'high risk' text adds risk styling."""
        messages = [{"role": "assistant", "content": "High risk detected"}]
        display_chat_history(messages)
        call_arg = st.markdown.call_args[0][0]
        assert "high-risk" in call_arg

    def test_display_chat_history_multiple_messages(self):
        """Multiple messages → multiple markdown calls."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi back!"}
        ]
        display_chat_history(messages)
        assert st.markdown.call_count == len(messages)


# --------------------------------------------------------------------
# 🚨 Fraud Visualizer Tests
# --------------------------------------------------------------------
class TestFraudVisualizer:
    def test_show_fraud_viz_no_alarms(self):
        """If no alarms → shows success message and pie chart."""
        data = {
            "probability": 0,
            "decision": "Approve",
            "alarms": [],
            "explanation": "Low risk"
        }
        show_fraud_viz(data)
        st.plotly_chart.assert_called_once()
        st.success.assert_called_once()
        st.markdown.assert_called()  # decision badge exists

    def test_show_fraud_viz_with_alarms(self):
        """With alarms → displays icons, warnings, and explanation."""
        data = {
            "probability": 75,
            "decision": "Reject",
            "alarms": [
                {"type": "high_amount", "description": "Exceeds limit", "severity": "high"}
            ],
            "explanation": "Fraud risk high"
        }
        show_fraud_viz(data)
        st.plotly_chart.assert_called_once()
        st.image.assert_called_with("static/icons/warning.png", width=20)
        st.expander.assert_called_once_with("Explanation")

    def test_show_fraud_viz_badge_class(self):
        """Decision badge has correct CSS class."""
        data = {"probability": 50, "decision": "Review", "alarms": [], "explanation": ""}
        show_fraud_viz(data)
        badge_html = st.markdown.call_args_list[0][0][0]
        assert "decision-review" in badge_html


# --------------------------------------------------------------------
# 📋 Claim Form Tests
# --------------------------------------------------------------------
class TestClaimForm:
    @patch("frontend.components.claim_form.st.file_uploader", return_value=None)
    def test_claim_input_form_manual_submit(self, mock_uploader):
        """Valid manual form submission returns a claim dict."""
        with patch("frontend.components.claim_form.st.number_input", side_effect=[5000.0, 0]), \
             patch("frontend.components.claim_form.st.text_input", side_effect=["ABC Clinic", "New York"]), \
             patch("frontend.components.claim_form.st.text_area", return_value="Test notes"), \
             patch("frontend.components.claim_form.st.checkbox", return_value=False), \
             patch("frontend.components.claim_form.st.form_submit_button", return_value=True):

            result = claim_input_form()
            assert result is not None
            assert result["amount"] == 5000.0
            assert result["provider"] == "ABC Clinic"
            assert "Test notes" in result["notes"]

    @patch("frontend.components.claim_form.st.file_uploader")
    @patch("utils.api_client.call_process_invoice")
    def test_claim_input_form_upload_success(self, mock_api, mock_uploader):
        """Upload file → Calls backend OCR and returns extracted data."""
        mock_file = MagicMock(name="invoice.pdf")
        mock_uploader.return_value = mock_file
        mock_api.return_value = {"amount": 2000, "provider": "Mock Clinic"}

        with patch("frontend.components.claim_form.st.button", return_value=True):
            result = claim_input_form()
            mock_api.assert_called_once_with(mock_file, ANY)
            assert result["provider"] == "Mock Clinic"

    @patch("frontend.components.claim_form.st.file_uploader")
    def test_claim_input_form_upload_failure(self, mock_uploader):
        """Failed OCR extraction → st.error called."""
        mock_uploader.return_value = MagicMock()
        with patch("utils.api_client.call_process_invoice", return_value=None), \
             patch("frontend.components.claim_form.st.button", return_value=True):
            result = claim_input_form()
            st.error.assert_called_once()
            assert result is None


# --------------------------------------------------------------------
# 📊 Result Panel Tests
# --------------------------------------------------------------------
class TestResultPanel:
    def test_display_results_fraud(self):
        """Fraud results render metrics, alarms, and explanation."""
        data = {
            "fraud_probability": 75.0,
            "decision": "Reject",
            "alarms": [{"type": "blacklist_hit", "description": "In blacklist"}],
            "explanation": "High risk detected"
        }
        display_results(data)
        st.metric.assert_any_call("Fraud Probability", "75.0%")
        st.metric.assert_any_call("Decision", "Reject")
        st.warning.assert_called_once()
        st.info.assert_called_once()

    def test_display_results_guidance(self):
        """Guidance results render text, docs, and relevance."""
        data = {
            "guidance": {"response": "Provide ID.", "required_docs": ["ID", "Invoice"]},
            "relevance_score": 0.8
        }
        display_results(data)
        st.markdown.assert_any_call("**Response:** Provide ID.")
        st.info.assert_any_call("• ID")
        st.caption.assert_called_once()

    def test_display_results_empty(self):
        """Empty input → gracefully skip rendering."""
        data = {}
        display_results(data)
        st.subheader.assert_not_called()
