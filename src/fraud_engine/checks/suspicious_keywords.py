def check(claim):
    keywords = ["scam", "fake", "staged"]
    notes = claim.notes or ""
    return any(k in notes.lower() for k in keywords)
