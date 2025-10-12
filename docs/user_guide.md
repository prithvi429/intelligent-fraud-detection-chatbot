
**Key Notes**:
- **Schema**: Table for DB structure.
- **Hybrid**: Explains Pinecone vs. DB fallback.
- **Examples**: Sample entries.

---

### `docs/user_guide.md` (User and Developer Guide)
**File: `docs/user_guide.md`**
```markdown
# User Guide

This guide covers usage for **end-users** (claim submitters) and **developers** (extending the project). The chatbot helps score claims for fraud and answer policy questions via a simple web interface.

## End-User Guide (Chatbot Usage)

### Accessing the App
- **Local Demo**: Run `streamlit run frontend/app.py` (http://localhost:8501).
- **Production**: Deployed at [your-domain.com](your-domain.com) (AWS S3/Amplify hosting).
- **Mobile**: Responsive; use browser (Chrome/Safari recommended).

### Chat Mode
1. **Select "Chat"** in sidebar.
2. **Type Message**:
   - **Claim Scoring**: "Score this claim: $15,000 accident in LA, reported 10 days late, provider shady_clinic, notes: staged crash."
     - Bot analyzes: Alarms (e.g., high amount, late, blacklist), ML prob (e.g., 75%), decision (Reject).
     - Shows: Pie chart (risk %), alarm list (with icons), explanation.
   - **Policy Questions**: "What documents do I need?" or "Why was my claim rejected?"
     - Bot searches policies: Returns answer + docs (e.g., "ID, invoice") + relevance score.
3. **View History**: Messages persist (last 20); clear via sidebar.
4. **Examples**:
   - Low Risk: "Normal $2,000 claim, reported today." → Approve (0 alarms).
   - High Risk: "Staged accident quick cash, new bank." → Reject (multiple alarms).

### Submit Claim Mode
1. **Select "Submit Claim"** in sidebar.
2. **Manual Entry**:
   - Fill form: Amount, delay days, provider, notes, location, new bank checkbox.
   - Click "Analyze Claim" → Results (same as chat: viz, alarms).
3. **File Upload**:
   - Drag PDF/image (invoice) → Backend OCR extracts (amount, date, provider).
   - Auto-fills form → Analyze.
   - Supported: PDF/JPG/PNG (<10MB).
4. **Results**: Decision badge (green/yellow/red), expandable explanation.

### Tips
- **Privacy**: Claimant IDs anonymized (hashed). No PII stored.
- **Errors**: If backend down, retry or contact support.
- **Support**: For appeals, bot provides docs/form.

## Developer Guide

### Project Setup
1. **Clone & Env**:
   ```bash
   git clone <repo>
   cd <project>
   cp .env.example .env  # Fill AWS keys, DB password, API keys