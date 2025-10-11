def check(claim):
    try:
        return claim.amount and claim.amount > 10000
    except Exception:
        return False
