from src.fraud_engine.checks import high_amount

def run_all(claim):
    alarms = []
    if high_amount.check(claim):
        alarms.append("high_amount")
    return alarms
