from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

payload = {
    "amount": 15000.0,
    "report_delay_days": 10,
    "provider": "shady_clinic",
    "notes": "Staged accident quick cash",
    "claimant_id": "api_test_user",
    "location": "Los Angeles, CA",
    "is_new_bank": True
}

r = client.post("/api/v1/score_claim", json=payload)
print("STATUS:", r.status_code)
print("TEXT:", r.text)
try:
    print("JSON:", r.json())
except Exception as e:
    print("Could not parse JSON:", e)
