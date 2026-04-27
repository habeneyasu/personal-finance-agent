"""Income Agent Lambda handler — FastAPI + Mangum."""
import json
from decimal import Decimal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from src.shared.auth import AuthError, get_user_id_from_event
from src.shared.db import get_connection, get_cursor
from src.shared.exceptions import handle_unhandled_exception
from src.shared.logger import Logger
from src.income_agent.models import IncomeEntry, IncomeEntryCreate
from src.shared.cors import add_cors_middleware

app = FastAPI(title="Income Agent")
add_cors_middleware(app)
_logger = Logger(service="income-agent")


def _error(error: str, detail: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": error, "detail": detail, "status": status})


def ensure_local_dev_user_exists(user_id: str) -> bool:
    """Ensure local dev user exists in database."""
    if user_id != "00000000-0000-0000-0000-000000000001":
        return True
    
    try:
        conn = get_connection()
        conn.autocommit = True  # Ensure immediate commit
        with get_cursor(conn) as cur:
            cur.execute(
                "INSERT INTO users (id, email, hashed_password) VALUES (%s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (user_id, "dev@local.test", "local-dev-password")
            )
            _logger.info(
                "Ensured local dev user exists",
                user_id=str(user_id),
                operation="ensure_local_dev_user",
                status="ok",
            )
        conn.close()
        return True
    except Exception as e:
        _logger.error(
            f"Failed to create local dev user: {e}",
            user_id=str(user_id),
            operation="ensure_local_dev_user",
            status="error",
        )
        return False


@app.post("/v1/income", status_code=201)
async def create_income(request: Request):
    event = request.scope.get("aws.event", {})
    try:
        user_id = get_user_id_from_event(event)
    except AuthError as e:
        return _error("unauthorized", e.message, 401)

    try:
        body = await request.json()
        entry_in = IncomeEntryCreate(**body)
    except Exception as e:
        return _error("validation_error", str(e), 400)

    # Comprehensive logging and error handling for database operations
    _logger.info("Starting POST request", user_id=str(user_id), operation="create_income", status="ok")
    
    try:
        # Ensure local dev user exists
        if not ensure_local_dev_user_exists(user_id):
            _logger.error(
                "Failed to ensure user exists",
                user_id=str(user_id),
                operation="create_income",
                status="error",
            )
            return _error("database_error", "Failed to create local dev user", 500)
        
        _logger.info(
            "User ensured exists, proceeding with database operations",
            user_id=str(user_id),
            operation="create_income",
            status="ok",
        )
        
        conn = get_connection()
        _logger.info("Database connection established", user_id=str(user_id), operation="create_income", status="ok")
        
        try:
            with get_cursor(conn) as cur:
                _logger.info(
                    "Database cursor created, inserting income entry",
                    user_id=str(user_id),
                    operation="create_income",
                    status="ok",
                )
                
                # Insert income entry
                cur.execute(
                    "INSERT INTO income_entries (user_id, amount, source, date, notes) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "RETURNING id, user_id, amount, source, date, notes, created_at",
                    (user_id, str(entry_in.amount), entry_in.source, entry_in.date, entry_in.notes),
                )
                row = cur.fetchone()
                _logger.info(
                    f"Income entry inserted successfully: {row[0]}",
                    user_id=str(user_id),
                    operation="create_income",
                    status="ok",
                )
                
        except Exception as db_error:
            _logger.error(
                f"Database error during insertion: {db_error}",
                user_id=str(user_id),
                operation="create_income",
                status="error",
            )
            return _error("database_error", str(db_error), 500)
        finally:
            conn.close()
            _logger.info("Database connection closed", user_id=str(user_id), operation="create_income", status="ok")

    except Exception as e:
        _logger.error(
            f"Unexpected error in POST request: {e}",
            user_id=str(user_id),
            operation="create_income",
            status="error",
        )
        return _error("internal_server_error", str(e), 500)

    entry = IncomeEntry(id=row[0], user_id=row[1], amount=Decimal(str(row[2])),
                        source=row[3], date=row[4], notes=row[5], created_at=row[6])
    _logger.info("Income entry created", user_id=str(user_id), operation="create_income",
                 status="ok", entry_id=str(entry.id))
    return JSONResponse(status_code=201, content=json.loads(entry.model_dump_json()))


@app.post("/v1/test-user", status_code=200)
async def test_user_creation(request: Request):
    """Test endpoint to isolate user creation issue."""
    event = request.scope.get("aws.event", {})
    try:
        user_id = get_user_id_from_event(event)
    except AuthError as e:
        return _error("unauthorized", e.message, 401)

    try:
        success = ensure_local_dev_user_exists(user_id)
        if success:
            return JSONResponse(status_code=200, content={"message": "User creation successful", "user_id": user_id})
        else:
            return _error("user_creation_failed", "Failed to create user", 500)
    except Exception as e:
        _logger.error(
            f"Test user creation failed: {e}",
            user_id=str(user_id),
            operation="test_user_creation",
            status="error",
        )
        return _error("test_failed", str(e), 500)


@app.get("/v1/income")
async def list_income(request: Request):
    event = request.scope.get("aws.event", {})
    try:
        user_id = get_user_id_from_event(event)
    except AuthError as e:
        return _error("unauthorized", e.message, 401)

    # Test user creation
    try:
        success = ensure_local_dev_user_exists(user_id)
        if success:
            _logger.info(
                "User creation test successful",
                user_id=str(user_id),
                operation="list_income",
                status="ok",
            )
        else:
            _logger.error(
                "User creation test failed",
                user_id=str(user_id),
                operation="list_income",
                status="error",
            )
    except Exception as e:
        _logger.error(
            f"User creation test exception: {e}",
            user_id=str(user_id),
            operation="list_income",
            status="error",
        )

    conn = get_connection()
    try:
        with get_cursor(conn) as cur:
            cur.execute(
                "SELECT id, user_id, amount, source, date, notes, created_at "
                "FROM income_entries "
                "WHERE user_id = %s "
                "ORDER BY date DESC",
                (user_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    entries = [
        IncomeEntry(
            id=row[0],
            user_id=row[1],
            amount=Decimal(str(row[2])),
            source=row[3],
            date=row[4],
            notes=row[5],
            created_at=row[6],
        )
        for row in rows
    ]
    _logger.info("Income entries listed", user_id=str(user_id), operation="list_income",
                 status="ok", count=len(entries))
    return JSONResponse(status_code=200, content=[json.loads(e.model_dump_json()) for e in entries])


handler = Mangum(app)


@handle_unhandled_exception
def lambda_handler(event: dict, context) -> dict:
    return handler(event, context)
