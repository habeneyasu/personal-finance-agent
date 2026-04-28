"""Database Reset Lambda handler - drops and recreates all tables."""
import json
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from src.shared.db import get_connection, get_cursor
from src.shared.logger import Logger
from src.shared.cors import add_cors_middleware

app = FastAPI(title="Database Reset Agent")
add_cors_middleware(app)
_logger = Logger(service="reset-agent")


def _error(error: str, detail: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": error, "detail": detail, "status": status})


@app.post("/reset-database", status_code=200)
async def reset_database(request: Request):
    """Reset database by dropping all tables and recreating schema."""
    operation = "reset_database"
    system_user_id = "system"
    conn = get_connection()
    try:
        conn.autocommit = True
        cursor = conn.cursor()
        
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
                _logger.info("Dropped table", user_id=system_user_id, operation=operation, status="ok")
            except Exception as e:
                _logger.warning(
                    f"Warning dropping table: {e}",
                    user_id=system_user_id,
                    operation=operation,
                    status="warning",
                )
        
        # Run migration to recreate schema
        from scripts.migrate import DDL_STATEMENTS
        
        for label, sql in DDL_STATEMENTS:
            try:
                cursor.execute(sql)
                _logger.info(
                    f"Migration completed: {label}",
                    user_id=system_user_id,
                    operation=operation,
                    status="ok",
                )
            except Exception as exc:
                _logger.error(
                    f"Migration failed: {label} — {exc}",
                    user_id=system_user_id,
                    operation=operation,
                    status="error",
                )
                return _error("migration_failed", str(exc), 500)
        
        # Create test user for development
        test_user_id = "00000000-0000-0000-0000-000000000001"
        test_email = "test@example.com"
        
        cursor.execute(
            "INSERT INTO users (id, email, hashed_password) VALUES (%s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING",
            (test_user_id, test_email, "test-password")
        )
        _logger.info(
            f"Created test user: {test_user_id}",
            user_id=system_user_id,
            operation=operation,
            status="ok",
        )
        
        cursor.close()
        conn.close()
        
        return JSONResponse(status_code=200, content={
            "message": "Database reset completed successfully",
            "test_user_id": test_user_id,
            "test_email": test_email
        })
        
    except Exception as exc:
        _logger.error(
            f"Database reset failed: {exc}",
            user_id=system_user_id,
            operation=operation,
            status="error",
        )
        return _error("reset_failed", str(exc), 500)


handler = Mangum(app)


def lambda_handler(event: dict, context) -> dict:
    return handler(event, context)
