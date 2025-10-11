from fastapi import APIRouter
from src.models.claim import ClaimData
from src.models.fraud import FraudResponse

router = APIRouter(prefix="/score_claim", tags=["score"])

@router.post("/", response_model=FraudResponse)
def score_claim(claim: ClaimData):
    alarms = []
    prob = 0.0
    if claim.amount and claim.amount > 10000:
        alarms.append("high_amount")
        prob += 0.7

    decision = "review"
    if prob >= 0.75:
        decision = "reject"
    elif prob < 0.4:
        decision = "approve"

    return FraudResponse(probability=prob, decision=decision, alarms=alarms, explanations={"note":"minimal stub"})
