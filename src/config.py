from dotenv import load_dotenv
import os

# Load from .env
load_dotenv()

# Database
DB_URL = os.getenv("DB_URL")
REDIS_URL = os.getenv("REDIS_URL")

# AWS / Storage
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION")

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# Fraud Thresholds
HIGH_AMOUNT_THRESHOLD = float(os.getenv("HIGH_AMOUNT_THRESHOLD", 10000))
ML_FRAUD_THRESHOLD = float(os.getenv("ML_FRAUD_THRESHOLD", 0.7))

# App Config
DEBUG = os.getenv("DEBUG", "True") == "True"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))
