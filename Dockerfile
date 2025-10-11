# =========================================================
# 🐍 Base Stage — Dependencies & Environment
# =========================================================
FROM python:3.10-slim AS base
WORKDIR /app

# Install system dependencies (Postgres, gcc for psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install only prod deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Download spaCy model (cached in layer)
RUN python -m spacy download en_core_web_sm

# Set default env vars
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    ENV=production

# =========================================================
# 🧪 Development Stage — Live Reload via Uvicorn
# =========================================================
FROM base AS dev
COPY . .
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# =========================================================
# 🚀 Production Stage — Optimized App Image
# =========================================================
FROM base AS prod

# Copy only necessary code (no .git, tests, etc.)
COPY src/ ./src/
COPY chatbot/ ./chatbot/
COPY ml/ ./ml/
COPY docs/ ./docs/
COPY .env.example ./

# Optional: Copy pre-trained model if small; otherwise mount volume
COPY ml/fraud_model.pkl ./ml/

# Download light SentenceTransformer (optional, but heavy)
# Better: Mount or lazy-load at runtime
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" || true

# Switch to non-root user for security
RUN useradd -m appuser
USER appuser

EXPOSE 8000

# Use more stable Uvicorn config (no reload, limited workers)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--no-access-log"]
