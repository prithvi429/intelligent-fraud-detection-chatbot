from src.models.claim import ClaimData
from src.fraud_engine.alarms import run_all

def test_high_amount_alarm():
    claim = ClaimData(claimant_id='1', amount=20000)
    alarms = run_all(claim)
    assert 'high_amount' in alarms
