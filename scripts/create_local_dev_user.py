#!/usr/bin/env python3
"""
Create local dev user in database for testing.

This script creates the local dev user that the auth system expects
when running in local development mode.
"""

import os
import sys

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.shared.db import get_connection, get_cursor


def create_local_dev_user() -> bool:
    """Create the local dev user if it doesn't exist."""
    local_dev_user_id = "00000000-0000-0000-0000-000000000001"
    local_dev_email = "dev@local.test"
    
    print("Connecting to database...")
    try:
        conn = get_connection()
    except Exception as exc:
        print(f"ERROR: Could not connect to database: {exc}")
        return False
    
    try:
        with get_cursor(conn) as cur:
            # Check if user already exists
            cur.execute("SELECT id FROM users WHERE id = %s", (local_dev_user_id,))
            existing_user = cur.fetchone()
            
            if existing_user:
                print(f"Local dev user already exists: {local_dev_user_id}")
                return True
            
            # Create the local dev user
            cur.execute(
                "INSERT INTO users (id, email, hashed_password) VALUES (%s, %s, %s)",
                (local_dev_user_id, local_dev_email, "local-dev-password")
            )
            
            print(f"Created local dev user: {local_dev_user_id} ({local_dev_email})")
            return True
            
    except Exception as exc:
        print(f"ERROR: Failed to create local dev user: {exc}")
        return False
    finally:
        conn.close()


def main() -> None:
    success = create_local_dev_user()
    if success:
        print("Local dev user creation completed successfully.")
        sys.exit(0)
    else:
        print("Local dev user creation failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
