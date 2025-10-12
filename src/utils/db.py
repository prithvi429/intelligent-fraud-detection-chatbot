"""
Database Utility
----------------
Manages Postgres (or SQLite fallback) connection, table creation, seeding,
and helper functions for claims, blacklist, and policy guidance.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import List, Optional, Dict, Any
from src.config import config
from src.utils.logger import logger
from src.models.fraud import Decision
from src.models.policy import PolicyGuidance
from src.models.claim import ClaimData

# =========================================================
# ⚙️ Database Setup
# =========================================================
Base = declarative_base()

try:
    engine = create_engine(
        config.DB_URL,
        echo=config.DEBUG,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={"connect_timeout": 10},
    )
    logger.info(f"✅ Database engine initialized: {config.DB_URL}")
except Exception as e:
    logger.error(f"❌ Database connection error: {e}")
    raise

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    """FastAPI dependency for DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================================================
# 🧱 Table Initialization
# =========================================================
def init_db() -> None:
    """
    Initialize core tables:
    - claims
    - blacklist
    - policies
    Called automatically at startup or in dev mode.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS claims (
                    id SERIAL PRIMARY KEY,
                    claimant_id VARCHAR(255) NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    report_delay_days INTEGER DEFAULT 0,
                    provider VARCHAR(255) NOT NULL,
                    notes TEXT,
                    location VARCHAR(255),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_new_bank BOOLEAN DEFAULT FALSE,
                    fraud_probability FLOAT DEFAULT 0.0,
                    decision VARCHAR(20) DEFAULT 'Review',
                    alarms JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    provider VARCHAR(255) PRIMARY KEY,
                    reason TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS policies (
                    id SERIAL PRIMARY KEY,
                    query VARCHAR(500) NOT NULL UNIQUE,
                    response TEXT NOT NULL,
                    required_docs TEXT[],
                    source VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            seed_blacklist(conn)
            seed_policies(conn)
            conn.commit()
            logger.info("✅ Database tables created and seeded.")
    except Exception as e:
        logger.error(f"❌ DB init error: {e}")
        raise


# =========================================================
# 🌐 Seed Data
# =========================================================
def seed_blacklist(conn) -> None:
    """Add default blacklisted providers."""
    blacklist_data = [
        ("shady_clinic", "Past overbilling fraud"),
        ("fake_vendor", "Reported fake invoices"),
        ("ghost_hospital", "Non-existent provider"),
    ]
    for provider, reason in blacklist_data:
        conn.execute(
            text("INSERT INTO blacklist (provider, reason) VALUES (:provider, :reason) ON CONFLICT DO NOTHING"),
            {"provider": provider, "reason": reason},
        )

def seed_policies(conn) -> None:
    """Insert default policy guidance data."""
    policies = [
        (
            "What documents are needed?",
            "Provide ID, receipts, and incident proof for faster approval.",
            ["Government ID", "Receipt", "Incident report"],
            "Policy Playbook v1.0",
        ),
        (
            "Why was my claim rejected?",
            "High fraud score or missing documents often cause rejections.",
            ["Appeal form", "Additional proof"],
            "Fraud Policy v1.0",
        ),
    ]
    for q, r, d, s in policies:
        conn.execute(
            text(
                "INSERT INTO policies (query, response, required_docs, source) VALUES (:q, :r, :d, :s) ON CONFLICT DO NOTHING"
            ),
            {"q": q, "r": r, "d": d, "s": s},
        )


# =========================================================
# 🏥 Blacklist Utilities
# =========================================================
def get_blacklist_providers(db: Session) -> List[str]:
    """Fetch all blacklisted provider names."""
    result = db.execute(text("SELECT provider FROM blacklist"))
    providers = [row[0].lower() for row in result.fetchall()]
    logger.debug(f"Loaded {len(providers)} blacklisted providers.")
    return providers


# =========================================================
# 💾 Claim Utilities
# =========================================================
def save_claim_to_db(
    claim: ClaimData,
    db: Session,
    fraud_prob: float,
    decision: Decision,
    alarms: List[Dict[str, Any]],
) -> int:
    """Save a claim record with fraud metadata."""
    try:
        result = db.execute(
            text("""
                INSERT INTO claims (
                    claimant_id, amount, report_delay_days, provider, notes, location,
                    timestamp, is_new_bank, fraud_probability, decision, alarms
                ) VALUES (
                    :claimant_id, :amount, :delay, :provider, :notes, :loc,
                    :ts, :is_new, :fraud, :decision, :alarms
                ) RETURNING id
            """),
            {
                "claimant_id": claim.claimant_id,
                "amount": claim.amount,
                "delay": claim.report_delay_days,
                "provider": claim.provider,
                "notes": claim.notes,
                "loc": claim.location,
                "ts": claim.timestamp,
                "is_new": claim.is_new_bank,
                "fraud": fraud_prob,
                "decision": decision.value,
                "alarms": [a.dict() for a in alarms],
            },
        )
        claim_id = result.fetchone()[0]
        db.commit()
        logger.debug(f"💾 Claim saved ID={claim_id} for {claim.claimant_id}")
        return claim_id
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error saving claim: {e}")
        raise


def get_claimant_history(claimant_id: str, db: Session, months: int = 12) -> Dict[str, Any]:
    """Fetch claimant’s historical claim stats."""
    try:
        result = db.execute(
            text("""
                SELECT COUNT(*) AS count, MAX(created_at) AS last_date, SUM(amount) AS total_amount
                FROM claims
                WHERE claimant_id = :id AND created_at > NOW() - INTERVAL ':months months'
            """),
            {"id": claimant_id, "months": months},
        )
        row = result.fetchone()
        return {
            "count": row[0],
            "last_claim_date": row[1],
            "total_amount": float(row[2]) if row[2] else 0.0,
        }
    except Exception as e:
        logger.warning(f"⚠️ Error getting claimant history: {e}")
        return {"count": 0, "last_claim_date": None, "total_amount": 0.0}


# =========================================================
# 📘 Policy Utilities
# =========================================================
def get_policy_from_db(query: str, db: Session) -> Optional[PolicyGuidance]:
    """Simple keyword search for a policy entry."""
    try:
        result = db.execute(
            text("SELECT query, response, required_docs, source FROM policies WHERE query ILIKE :q LIMIT 1"),
            {"q": f"%{query}%"},
        )
        row = result.fetchone()
        if row:
            return PolicyGuidance(
                query=row[0],
                response=row[1],
                required_docs=row[2] if isinstance(row[2], list) else row[2].split(","),
                source=row[3],
            )
    except Exception as e:
        logger.warning(f"⚠️ Policy lookup failed: {e}")
    return None


# =========================================================
# 🧪 Auto-init in Dev
# =========================================================
if config.DEBUG:
    try:
        init_db()
    except Exception:
        logger.warning("⚠️ Could not auto-initialize DB (possibly already set up).")
