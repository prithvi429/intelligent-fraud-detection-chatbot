from fastapi import APIRouter

router = APIRouter(prefix="/explain", tags=["explain"])

@router.get("/{alarm_type}")
def explain_alarm(alarm_type: str):
    explanations = {
        "high_amount": "Claim amount exceeds configured threshold.",
        "location_mismatch": "Claim location differs significantly from policyholder address.",
    }
    return {"alarm": alarm_type, "explanation": explanations.get(alarm_type, "No explanation available.")}
