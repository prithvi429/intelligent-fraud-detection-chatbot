"""
DB Migrations Script (Alembic)
------------------------------
Initializes Alembic (if not exists), generates or applies migrations.

Usage:
  python infra/scripts/migrate_data.py init
  python infra/scripts/migrate_data.py revision add_fraud_score
  python infra/scripts/migrate_data.py upgrade head
  python infra/scripts/migrate_data.py downgrade -1

Requires:
  - .env with DB_URL
  - alembic.ini in project root
  - src/models with Base.metadata

Alembic paths:
  - alembic.ini → root
  - alembic/versions → migration files
"""

import os
import sys
import argparse
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from src.utils.db import engine
from src.models import Base

# Load environment variables
load_dotenv()

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
ALEMBIC_CFG_PATH = os.path.join(ROOT_DIR, "alembic.ini")
MIGRATIONS_DIR = os.path.join(ROOT_DIR, "alembic/versions")

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def ensure_alembic_env():
    """Ensure alembic directory and ini file exist."""
    if not os.path.exists(ALEMBIC_CFG_PATH):
        print("❌ alembic.ini not found. Run: alembic init alembic")
        sys.exit(1)
    if not os.path.exists(MIGRATIONS_DIR):
        os.makedirs(MIGRATIONS_DIR, exist_ok=True)


def get_alembic_config() -> Config:
    """Load Alembic configuration with DB_URL from .env."""
    ensure_alembic_env()
    cfg = Config(ALEMBIC_CFG_PATH)
    db_url = os.getenv("DB_URL", "sqlite:///alembic_local.db")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


# --------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------
def init_alembic():
    """Initialize Alembic environment (one-time setup)."""
    if os.path.exists(ALEMBIC_CFG_PATH):
        print("✅ Alembic already initialized.")
        return
    os.system("alembic init alembic")
    print("✅ Alembic environment created. Configure env.py to import src.models.Base.metadata.")


def create_revision(name: str):
    """Create new revision (autogenerate schema changes)."""
    cfg = get_alembic_config()
    print(f"🧩 Generating revision: {name} ...")
    command.revision(cfg, message=name, autogenerate=True)
    print("✅ Revision file created under alembic/versions/")


def upgrade_db(revision: str = "head"):
    """Upgrade database schema to a specific revision."""
    cfg = get_alembic_config()
    print(f"🚀 Upgrading database to revision: {revision}")
    command.upgrade(cfg, revision)
    print("✅ Upgrade complete.")


def downgrade_db(revision: str = "-1"):
    """Downgrade database to a specific revision."""
    cfg = get_alembic_config()
    print(f"↩️ Downgrading database to revision: {revision}")
    command.downgrade(cfg, revision)
    print("✅ Downgrade complete.")


# --------------------------------------------------------------------
# CLI Entry Point
# --------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Alembic Database Migration Utility")

    subparsers = parser.add_subparsers(dest="command", help="Alembic commands")

    # init
    subparsers.add_parser("init", help="Initialize Alembic environment")

    # revision
    rev_parser = subparsers.add_parser("revision", help="Create new revision")
    rev_parser.add_argument("name", help="Migration name (e.g., add_claim_status)")

    # upgrade
    up_parser = subparsers.add_parser("upgrade", help="Upgrade to revision (default: head)")
    up_parser.add_argument("revision", nargs="?", default="head", help="Revision ID or 'head'")

    # downgrade
    down_parser = subparsers.add_parser("downgrade", help="Downgrade one or more revisions")
    down_parser.add_argument("revision", nargs="?", default="-1", help="Revision ID or '-1'")

    args = parser.parse_args()

    if args.command == "init":
        init_alembic()
    elif args.command == "revision":
        create_revision(args.name)
    elif args.command == "upgrade":
        upgrade_db(args.revision)
    elif args.command == "downgrade":
        downgrade_db(args.revision)
    else:
        parser.print_help()
