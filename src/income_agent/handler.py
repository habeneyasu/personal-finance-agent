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

app = FastAPI(title="Income Agent")
_logger = Logger(service="income-agent")


def _error(error: str, detail: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": error, "detail": detail, "status": status})


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

    conn = get_connection()
    try:
        with get_cursor(conn) as cur:
            cur.execute(
                "INSERT INTO income_entries (user_id, amount, source, date, notes) "
                "VALUES (%s, %s, %s, %s, %s) "
                "RETURNING id, user_id, amount, source, date, notes, created_at",
                (user_id, str(entry_in.amount), entry_in.source, entry_in.date, entry_in.notes),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    entry = IncomeEntry(id=row[0], user_id=row[1], amount=Decimal(str(row[2])),
                        source=row[3], date=row[4], notes=row[5], created_at=row[6])
    _logger.info("Income entry created", user_id=str(user_id), operation="create_income",
                 status="ok", entry_id=str(entry.id))
    return JSONResponse(status_code=201, content=json.loads(entry.model_dump_json()))


@app.get("/v1/income")
async def list_income(request: Request):
    event = request.scope.get("aws.event", {})
    try:
        user_id = get_user_id_from_event(event)
    except AuthError as e:
        return _error("unauthorized", e.message, 401)

    conn = get_connection()
    try:
        with get_cursor(conn) as cur:
            cur.execute(
                "SELECT id, user_id, amount, source, date, notes, created_at "
                "FROM income_entries WHERE user_id = %s ORDER BY date DESC",
                (user_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    entries = [IncomeEntry(id=r[0], user_id=r[1], amount=Decimal(str(r[2])),
                           source=r[3], date=r[4], notes=r[5], created_at=r[6])
               for r in rows]
    _logger.info("Income entries listed", user_id=str(user_id), operation="list_income",
                 status="ok", count=len(entries))
    return JSONResponse(status_code=200, content=[json.loads(e.model_dump_json()) for e in entries])


handler = Mangum(app)


@handle_unhandled_exception
def lambda_handler(event: dict, context) -> dict:
    return handler(event, context)
