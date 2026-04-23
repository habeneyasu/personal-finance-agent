"""
Database migration script for PFIP MVP.

Runs the full DDL in order. All statements are idempotent (IF NOT EXISTS).

Usage:
    python scripts/migrate.py --env staging
    python scripts/migrate.py --env local

Credentials are read from:
  - AWS Secrets Manager via DB_SECRET_ARN or DB_SECRET_NAME env var, OR
  - Direct env vars: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""

import argparse
import sys
import os

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.shared.db import get_connection  # noqa: E402

# ---------------------------------------------------------------------------
# DDL statements — executed in order
# ---------------------------------------------------------------------------

DDL_STATEMENTS = [
    (
        "Enable pgcrypto extension",
        'CREATE EXTENSION IF NOT EXISTS "pgcrypto";',
    ),
    (
        "Create users table",
        """
        CREATE TABLE IF NOT EXISTS users (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email             TEXT NOT NULL UNIQUE,
            hashed_password   TEXT,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
    ),
    (
        "Add hashed_password column if missing",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password TEXT;",
    ),
    (
        "Create income_entries table",
        """
        CREATE TABLE IF NOT EXISTS income_entries (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            amount      NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
            source      TEXT NOT NULL,
            date        DATE NOT NULL,
            notes       TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
    ),
    (
        "Create index idx_income_user_date",
        "CREATE INDEX IF NOT EXISTS idx_income_user_date ON income_entries(user_id, date DESC);",
    ),
    (
        "Create expense_entries table",
        """
        CREATE TABLE IF NOT EXISTS expense_entries (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            amount      NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
            merchant    TEXT NOT NULL,
            category    TEXT NOT NULL DEFAULT 'Other',
            date        DATE NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
    ),
    (
        "Create index idx_expense_user_date",
        "CREATE INDEX IF NOT EXISTS idx_expense_user_date ON expense_entries(user_id, date DESC);",
    ),
    (
        "Create savings_goals table",
        """
        CREATE TABLE IF NOT EXISTS savings_goals (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name            TEXT NOT NULL,
            target_amount   NUMERIC(12, 2) NOT NULL CHECK (target_amount > 0),
            current_amount  NUMERIC(12, 2) NOT NULL DEFAULT 0,
            target_date     DATE NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
    ),
    (
        "Create index idx_goals_user",
        "CREATE INDEX IF NOT EXISTS idx_goals_user ON savings_goals(user_id);",
    ),
]


def run_migrations(env: str) -> bool:
    """Run all DDL statements. Returns True if all succeeded, False otherwise."""
    print(f"[{env}] Connecting to database...")
    try:
        conn = get_connection()
    except Exception as exc:
        print(f"[{env}] ERROR: Could not connect to database: {exc}")
        return False

    conn.autocommit = True  # DDL statements don't need explicit transaction management
    cursor = conn.cursor()

    all_ok = True
    for label, sql in DDL_STATEMENTS:
        try:
            cursor.execute(sql)
            print(f"[{env}] OK: {label}")
        except Exception as exc:
            print(f"[{env}] FAILED: {label} — {exc}")
            all_ok = False

    cursor.close()
    conn.close()
    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(description="PFIP database migration script")
    parser.add_argument(
        "--env",
        default="staging",
        help="Environment name for logging context (default: staging)",
    )
    args = parser.parse_args()

    success = run_migrations(args.env)
    if success:
        print(f"[{args.env}] Migration completed successfully.")
        sys.exit(0)
    else:
        print(f"[{args.env}] Migration completed with errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
