"""
Demo seed script for PFIP MVP.

Populates the database with realistic demo data for the Friday demo:
  - 1 demo user (fixed UUID: 00000000-0000-0000-0000-000000000001)
  - 3 months of income entries (salary + freelance)
  - 2 months of categorized expenses across all 8 categories
  - 2 active savings goals (vacation, emergency fund)

Usage:
    python3 scripts/seed_demo.py --env local
    python3 scripts/seed_demo.py --env staging
"""

import argparse
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5433")
os.environ.setdefault("DB_NAME", "pfip")
os.environ.setdefault("DB_USER", "pfip_admin")
os.environ.setdefault("DB_PASSWORD", "pfip_local_password")

from src.shared.db import get_connection, get_cursor  # noqa: E402

# Fixed demo user UUID — matches local-dev-user in auth.py
DEMO_USER_ID = "00000000-0000-0000-0000-000000000001"
DEMO_EMAIL = "demo@pfip.dev"


def create_demo_user(conn) -> str:
    """Create or retrieve the demo user. Returns user UUID."""
    import bcrypt
    hashed = bcrypt.hashpw(b"Demo1234!", bcrypt.gensalt()).decode()

    with get_cursor(conn) as cur:
        cur.execute(
            """
            INSERT INTO users (id, email, hashed_password)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email, hashed_password = EXCLUDED.hashed_password
            RETURNING id
            """,
            (DEMO_USER_ID, DEMO_EMAIL, hashed),
        )
        row = cur.fetchone()
    return str(row[0])


def seed_income(conn, user_id: str) -> None:
    """Insert 3 months of income entries (salary + freelance)."""
    today = date.today()

    entries = []
    for months_ago in range(3, 0, -1):
        # Salary on the 1st of each month
        salary_date = date(today.year, today.month, 1) - timedelta(days=months_ago * 30)
        entries.append((user_id, "5000.00", "Salary", salary_date.isoformat(), "Monthly salary"))

        # Freelance mid-month
        freelance_date = salary_date + timedelta(days=14)
        amount = ["950.00", "1200.00", "800.00"][months_ago - 1]
        entries.append((user_id, amount, "Freelance", freelance_date.isoformat(), "Freelance project"))

    with get_cursor(conn) as cur:
        cur.executemany(
            """
            INSERT INTO income_entries (user_id, amount, source, date, notes)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            entries,
        )
    print(f"  ✓ Inserted {len(entries)} income entries")


def seed_expenses(conn, user_id: str) -> None:
    """Insert 2 months of expenses across all 8 categories."""
    today = date.today()

    def d(days_ago: int) -> str:
        return (today - timedelta(days=days_ago)).isoformat()

    entries = [
        # Groceries
        (user_id, "87.50",  "Whole Foods",        "Groceries",      d(3)),
        (user_id, "62.30",  "Trader Joe's",       "Groceries",      d(18)),
        (user_id, "94.10",  "Safeway",            "Groceries",      d(35)),
        (user_id, "55.80",  "Whole Foods",        "Groceries",      d(52)),
        # Transportation
        (user_id, "24.50",  "Uber",               "Transportation", d(2)),
        (user_id, "18.75",  "Lyft",               "Transportation", d(10)),
        (user_id, "45.00",  "Shell Gas Station",  "Transportation", d(22)),
        (user_id, "32.00",  "Uber",               "Transportation", d(40)),
        # Dining
        (user_id, "68.00",  "The Capital Grille", "Dining",         d(5)),
        (user_id, "32.50",  "Chipotle",           "Dining",         d(14)),
        (user_id, "47.80",  "Sushi Palace",       "Dining",         d(28)),
        (user_id, "22.00",  "Starbucks",          "Dining",         d(45)),
        # Entertainment
        (user_id, "15.99",  "Netflix",            "Entertainment",  d(1)),
        (user_id, "12.99",  "Spotify",            "Entertainment",  d(1)),
        (user_id, "28.00",  "AMC Theaters",       "Entertainment",  d(20)),
        (user_id, "59.99",  "Steam Games",        "Entertainment",  d(38)),
        # Utilities
        (user_id, "120.00", "Electric Company",   "Utilities",      d(8)),
        (user_id, "85.00",  "Internet Provider",  "Utilities",      d(8)),
        (user_id, "115.00", "Electric Company",   "Utilities",      d(38)),
        # Healthcare
        (user_id, "25.00",  "CVS Pharmacy",       "Healthcare",     d(12)),
        (user_id, "150.00", "Dental Clinic",      "Healthcare",     d(30)),
        # Shopping
        (user_id, "89.99",  "Amazon",             "Shopping",       d(7)),
        (user_id, "145.00", "Nike Store",         "Shopping",       d(25)),
        (user_id, "67.50",  "Target",             "Shopping",       d(42)),
        # Other
        (user_id, "35.00",  "Post Office",        "Other",          d(15)),
        (user_id, "200.00", "Car Insurance",      "Other",          d(32)),
    ]

    with get_cursor(conn) as cur:
        cur.executemany(
            """
            INSERT INTO expense_entries (user_id, amount, merchant, category, date)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            entries,
        )
    print(f"  ✓ Inserted {len(entries)} expense entries across all 8 categories")


def seed_goals(conn, user_id: str) -> None:
    """Insert 2 active savings goals."""
    today = date.today()
    vacation_date = (today + timedelta(days=180)).isoformat()
    emergency_date = (today + timedelta(days=365)).isoformat()

    goals = [
        (user_id, "Vacation Fund",   "3000.00", "500.00",  vacation_date),
        (user_id, "Emergency Fund",  "10000.00", "1200.00", emergency_date),
    ]

    with get_cursor(conn) as cur:
        cur.executemany(
            """
            INSERT INTO savings_goals (user_id, name, target_amount, current_amount, target_date)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            goals,
        )
    print(f"  ✓ Inserted {len(goals)} savings goals")


def clear_existing_data(conn, user_id: str) -> None:
    """Remove existing demo data to allow clean re-seeding."""
    with get_cursor(conn) as cur:
        cur.execute("DELETE FROM savings_goals WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM expense_entries WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM income_entries WHERE user_id = %s", (user_id,))
    print("  ✓ Cleared existing demo data")


def main() -> None:
    parser = argparse.ArgumentParser(description="PFIP demo seed script")
    parser.add_argument("--env", default="local", help="Environment (default: local)")
    parser.add_argument("--reset", action="store_true", help="Clear existing data before seeding")
    args = parser.parse_args()

    print(f"\n[{args.env}] PFIP Demo Seed Script")
    print("=" * 40)

    print(f"[{args.env}] Connecting to database...")
    conn = get_connection()

    print(f"[{args.env}] Creating demo user ({DEMO_USER_ID})...")
    user_id = create_demo_user(conn)
    print(f"  ✓ Demo user: {DEMO_EMAIL}")

    if args.reset:
        print(f"[{args.env}] Clearing existing data...")
        clear_existing_data(conn, user_id)

    print(f"[{args.env}] Seeding income entries...")
    seed_income(conn, user_id)

    print(f"[{args.env}] Seeding expense entries...")
    seed_expenses(conn, user_id)

    print(f"[{args.env}] Seeding savings goals...")
    seed_goals(conn, user_id)

    conn.close()
    print(f"\n[{args.env}] ✅ Seed complete!")
    print(f"  Dashboard: http://localhost:5173")
    print(f"  API:       http://localhost:8000")
    print(f"  MCP:       npx @modelcontextprotocol/inspector python3 scripts/run_mcp_local.py")


if __name__ == "__main__":
    main()
