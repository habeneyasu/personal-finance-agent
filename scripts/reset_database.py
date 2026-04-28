#!/usr/bin/env python3
"""
Reset database by dropping all tables and recreating them.

This script will:
1. Drop all existing tables (cascade)
2. Run full migration to recreate schema
3. Create a test user for development
"""

import os
import sys

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.shared.db import get_connection, get_cursor


def reset_database() -> bool:
    """Drop all tables and recreate schema."""
    print("Connecting to database...")
    try:
        conn = get_connection()
    except Exception as exc:
        print(f"ERROR: Could not connect to database: {exc}")
        return False
    
    conn.autocommit = True  # DDL statements don't need explicit transaction management
    cursor = conn.cursor()
    
    try:
        # Drop all tables in reverse order of dependencies
        drop_statements = [
            "DROP TABLE IF EXISTS llm_usage CASCADE;",
            "DROP TABLE IF EXISTS savings_goals CASCADE;", 
            "DROP TABLE IF EXISTS expense_entries CASCADE;",
            "DROP TABLE IF EXISTS income_entries CASCADE;",
            "DROP TABLE IF EXISTS users CASCADE;",
        ]
        
        for stmt in drop_statements:
            try:
                cursor.execute(stmt)
                print(f"✓ Dropped table")
            except Exception as e:
                print(f"⚠ Warning dropping table: {e}")
        
        # Now run full migration to recreate everything
        print("\nRunning migration to recreate schema...")
        from scripts.migrate import DDL_STATEMENTS, run_migrations
        
        # Run migration directly with current connection
        for label, sql in DDL_STATEMENTS:
            try:
                cursor.execute(sql)
                print(f"✓ {label}")
            except Exception as exc:
                print(f"✗ Failed: {label} — {exc}")
                return False
        
        # Create test user for development
        test_user_id = "00000000-0000-0000-0000-000000000001"
        test_email = "test@example.com"
        
        cursor.execute(
            "INSERT INTO users (id, email, hashed_password) VALUES (%s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING",
            (test_user_id, test_email, "test-password")
        )
        print(f"✓ Created test user: {test_user_id}")
        
        cursor.close()
        conn.close()
        print("\n✅ Database reset completed successfully!")
        return True
        
    except Exception as exc:
        print(f"ERROR: Failed to reset database: {exc}")
        cursor.close()
        conn.close()
        return False


def main() -> None:
    success = reset_database()
    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
