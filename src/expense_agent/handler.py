"""Expense Agent Lambda handler — FastAPI + Mangum."""
import json
from decimal import Decimal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from src.shared.auth import AuthError, get_user_id_from_event
from src.shared.db import get_connection, get_cursor
from src.shared.exceptions import handle_unhandled_exception
from src.shared.logger import Logger
from src.expense_agent.models import ExpenseEntry, ExpenseEntryCreate
from src.expense_agent.categorizer import categorize_expense
from src.shared.cors import add_cors_middleware

app = FastAPI(title="Expense Agent")
add_cors_middleware(app)
_logger = Logger(service="expense-agent")


def _error(error: str, detail: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": error, "detail": detail, "status": status})


@app.post("/v1/expenses", status_code=201)
async def create_expense(request: Request):
    event = request.scope.get("aws.event", {})
    try:
        user_id = get_user_id_from_event(event)
    except AuthError as e:
        return _error("unauthorized", e.message, 401)

    try:
        body = await request.json()
        entry_in = ExpenseEntryCreate(**body)
    except Exception as e:
        return _error("validation_error", str(e), 400)

    category = categorize_expense(entry_in.merchant, entry_in.amount, user_id=str(user_id))

    conn = get_connection()
    try:
        with get_cursor(conn) as cur:
            # Ensure local dev user exists for development
            if user_id == "00000000-0000-0000-0000-000000000001":
                cur.execute(
                    "INSERT INTO users (id, email, hashed_password) VALUES (%s, %s, %s) "
                    "ON CONFLICT (id) DO NOTHING",
                    (user_id, "dev@local.test", "local-dev-password")
                )
                _logger.info(
                    "Created local dev user",
                    user_id=str(user_id),
                    operation="create_expense",
                    status="ok",
                )
            
            cur.execute(
                "INSERT INTO expense_entries (user_id, amount, merchant, category, date) "
                "VALUES (%s, %s, %s, %s, %s) "
                "RETURNING id, user_id, amount, merchant, category, date, created_at",
                (user_id, str(entry_in.amount), entry_in.merchant, category, entry_in.date),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    entry = ExpenseEntry(id=row[0], user_id=row[1], amount=Decimal(str(row[2])),
                         merchant=row[3], category=row[4], date=row[5], created_at=row[6])
    _logger.info("Expense entry created", user_id=str(user_id), operation="create_expense",
                 status="ok", entry_id=str(entry.id), category=category)
    return JSONResponse(status_code=201, content=json.loads(entry.model_dump_json()))


@app.get("/v1/expenses")
async def list_expenses(request: Request):
    event = request.scope.get("aws.event", {})
    try:
        user_id = get_user_id_from_event(event)
    except AuthError as e:
        return _error("unauthorized", e.message, 401)

    conn = get_connection()
    try:
        with get_cursor(conn) as cur:
            cur.execute(
                "SELECT id, user_id, amount, merchant, category, date, created_at "
                "FROM expense_entries WHERE user_id = %s ORDER BY date DESC",
                (user_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    entries = [ExpenseEntry(id=r[0], user_id=r[1], amount=Decimal(str(r[2])),
                            merchant=r[3], category=r[4], date=r[5], created_at=r[6])
               for r in rows]
    _logger.info("Expense entries listed", user_id=str(user_id), operation="list_expenses",
                 status="ok", count=len(entries))
    return JSONResponse(status_code=200, content=[json.loads(e.model_dump_json()) for e in entries])


handler = Mangum(app)


@handle_unhandled_exception
def lambda_handler(event: dict, context) -> dict:
    return handler(event, context)
