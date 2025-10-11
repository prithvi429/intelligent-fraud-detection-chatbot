from fastapi import FastAPI

app = FastAPI(title="Insurance Fraud Chatbot API")

@app.get("/")
def root():
    return {"status": "ok", "message": "Insurance Fraud Detection"}
