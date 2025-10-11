def decide(prob, alarms):
    if prob >= 0.75:
        return "reject"
    elif prob < 0.4:
        return "approve"
    return "review"
