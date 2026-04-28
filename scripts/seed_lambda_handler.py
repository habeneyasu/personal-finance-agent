"""
One-shot seed Lambda handler.
Deploy temporarily, invoke, then delete.
"""
import json
import os
import sys

sys.path.insert(0, "/var/task")
os.environ.setdefault("ENVIRONMENT", "staging")

def lambda_handler(event, context):
    try:
        from scripts.seed_demo import (
            create_demo_user, seed_income, seed_expenses, seed_goals, clear_existing_data
        )
        from src.shared.db import get_connection

        conn = get_connection()
        user_id = create_demo_user(conn)
        clear_existing_data(conn, user_id)
        seed_income(conn, user_id)
        seed_expenses(conn, user_id)
        seed_goals(conn, user_id)
        conn.close()
        return {"statusCode": 200, "body": json.dumps({"status": "seeded", "user_id": user_id})}
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
