"""Savings Goal Agent Lambda handler — FastAPI + Mangum."""
import json
from decimal import Decimal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from src.shared.auth import AuthError, get_user_id_from_event
from src.shared.db import get_connection, get_cursor
from src.shared.exceptions import handle_unhandled_exception
from src.shared.logger import Logger
from src.savings_agent.models import SavingsGoal, SavingsGoalCreate, SavingsGoalWithProgress
from src.savings_agent.calculator import calculate_monthly_rate, calculate_progress, predict_completion
from src.shared.cors import add_cors_middleware

app = FastAPI(title="Savings Goal Agent")
add_cors_middleware(app)
_logger = Logger(service="savings-agent")


def _error(error: str, detail: str, status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": error, "detail": detail, "status": status},
    )


@app.post("/v1/goals", status_code=201)
async def create_goal(request: Request):
    event = request.scope.get("aws.event", {})

    try:
        user_id = get_user_id_from_event(event)
    except AuthError as e:
        return _error("unauthorized", e.message, 401)

    try:
        body = await request.json()
        goal_in = SavingsGoalCreate(**body)
    except Exception as e:
        return _error("validation_error", str(e), 400)

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
                    operation="create_goal",
                    status="ok",
                )
            
            cur.execute(
                "INSERT INTO savings_goals (user_id, name, target_amount, current_amount, initial_amount, target_date) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "RETURNING id, user_id, name, target_amount, current_amount, initial_amount, target_date, created_at",
                (user_id, goal_in.name, str(goal_in.target_amount), str(goal_in.initial_amount),
                 str(goal_in.initial_amount), goal_in.target_date),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    goal = SavingsGoal(
        id=row[0], user_id=row[1], name=row[2],
        target_amount=Decimal(str(row[3])),
        current_amount=Decimal(str(row[4])),
        initial_amount=Decimal(str(row[5])),
        target_date=row[6], created_at=row[7],
    )

    _logger.info(
        "Savings goal created",
        user_id=str(user_id),
        operation="create_goal",
        status="ok",
        goal_id=str(goal.id),
    )

    return JSONResponse(
        status_code=201,
        content=json.loads(goal.model_dump_json()),
    )


@app.get("/v1/goals")
async def list_goals(request: Request):
    event = request.scope.get("aws.event", {})

    try:
        user_id = get_user_id_from_event(event)
    except AuthError as e:
        return _error("unauthorized", e.message, 401)

    conn = get_connection()
    try:
        with get_cursor(conn) as cur:
            # Fetch all goals for user
            cur.execute(
                """
                SELECT id, user_id, name, target_amount, current_amount, initial_amount, target_date, created_at
                FROM savings_goals
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            goal_rows = cur.fetchall()

            results = []
            for row in goal_rows:
                goal_id = row[0]
                goal_created_at = row[7]

                # Income since goal creation
                cur.execute(
                    "SELECT amount FROM income_entries WHERE user_id = %s AND date >= %s",
                    (user_id, goal_created_at.date() if hasattr(goal_created_at, "date") else goal_created_at),
                )
                income_rows = cur.fetchall()

                # Expenses since goal creation
                cur.execute(
                    "SELECT amount FROM expense_entries WHERE user_id = %s AND date >= %s",
                    (user_id, goal_created_at.date() if hasattr(goal_created_at, "date") else goal_created_at),
                )
                expense_rows = cur.fetchall()

                current_amount = calculate_progress(goal_created_at, income_rows, expense_rows,
                                                    initial_amount=Decimal(str(row[5])))

                # Income and expenses for last 30 days (for monthly rate)
                cur.execute(
                    "SELECT amount, date FROM income_entries WHERE user_id = %s",
                    (user_id,),
                )
                all_income = cur.fetchall()

                cur.execute(
                    "SELECT amount, date FROM expense_entries WHERE user_id = %s",
                    (user_id,),
                )
                all_expenses = cur.fetchall()

                monthly_rate = calculate_monthly_rate(all_income, all_expenses)

                target_amount = Decimal(str(row[3]))
                predicted_date = predict_completion(current_amount, target_amount, monthly_rate)

                progress_pct = (
                    min(100.0, float(current_amount / target_amount * 100))
                    if target_amount > 0
                    else 0.0
                )

                # Update current_amount in DB
                cur.execute(
                    "UPDATE savings_goals SET current_amount = %s WHERE id = %s",
                    (str(current_amount), goal_id),
                )

                goal_with_progress = SavingsGoalWithProgress(
                    id=row[0],
                    user_id=row[1],
                    name=row[2],
                    target_amount=target_amount,
                    current_amount=current_amount,
                    initial_amount=Decimal(str(row[5])),
                    target_date=row[6],
                    created_at=goal_created_at,
                    progress_pct=progress_pct,
                    predicted_completion_date=predicted_date,
                )
                results.append(goal_with_progress)

    finally:
        conn.close()

    _logger.info(
        "Savings goals listed",
        user_id=str(user_id),
        operation="list_goals",
        status="ok",
        count=len(results),
    )

    return JSONResponse(
        status_code=200,
        content=[json.loads(g.model_dump_json()) for g in results],
    )


# Mangum adapter wraps the FastAPI app for Lambda
handler = Mangum(app)


@handle_unhandled_exception
def lambda_handler(event: dict, context) -> dict:
    return handler(event, context)
