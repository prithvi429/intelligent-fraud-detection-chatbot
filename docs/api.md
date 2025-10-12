# API Reference

This document describes the RESTful API for the **Insurance Fraud Detection Chatbot**.  
The backend is built with **FastAPI** and exposes endpoints for fraud scoring, alarm explanations, and policy guidance.

---

## Base URLs
- **Local:** `http://localhost:8000`
- **AWS (Production):** `https://<api-id>.execute-api.us-east-1.amazonaws.com/prod`

All endpoints are versioned under `/api/v1/` and return JSON.

---

## Authentication
| Environment | Auth Type | Header Example |
|--------------|------------|----------------|
| Development | None | *(Open for testing)* |
| Production | Bearer JWT | `Authorization: Bearer <token>` |

Optional endpoint `/api/v1/me` returns authenticated user info.

---

## Endpoints

---

### **1️⃣ POST /api/v1/score_claim**

Analyzes an insurance claim for potential fraud.  
The backend uses both **rule-based alarms** and an **ML model (SageMaker)**.

#### Request Body (JSON)
```json
{
  "amount": 15000.0,
  "report_delay_days": 10,
  "provider": "shady_clinic",
  "notes": "Staged accident for quick cash",
  "claimant_id": "user123",
  "location": "Los Angeles, CA",
  "is_new_bank": true
}
