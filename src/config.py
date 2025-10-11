import os
from dotenv import load_dotenv

load_dotenv()

FRAUD_THRESHOLDS = {
    "high_amount": float(os.getenv("FRAUD_THRESHOLDS_HIGH_AMOUNT", "10000"))
}

DATABASE_URL = os.getenv("DB_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
