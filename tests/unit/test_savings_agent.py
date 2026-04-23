"""Unit tests for the Savings Goal Agent Lambda handler and calculator."""
import json
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, call, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

# Set ENVIRONMENT=local before importing the app so auth is bypassed
os.environ.setdefault("ENVIRONMENT", "local")

from src.savings_agent.handler import app
from src.savings_agent.calculator import calculate_monthly_rate, calculate_progress, predict_completion

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = str(uuid4())
_NOW = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
_FUTURE_DATE = (date.today() + timedelta(days=365)).isoformat()


def _make_goal_row(
    goal_id=None,
    user_id=None,
    name="Vacation",
    target_amount="5000.00",
    current_amount="0.00",
    target_date=None,
    created_at=None,
):
    return (
        goal_id or uuid4(),
        user_id or uuid4(),
        name,
        Decimal(target_amount),
        Decimal(current_amount),
        target_date or (date.today() + timedelta(days=365)),
        created_at or _NOW,
    )


def _mock_conn_multi(side_effects):
    """Return a mock connection whose cursor.fetchone/fetchall cycle through side_effects."""
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


def _mock_conn(rows=None, insert_row=None):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = insert_row
    mock_cursor.fetchall.return_value = rows or []
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


# ---------------------------------------------------------------------------
# POST /v1/goals
# ---------------------------------------------------------------------------

class TestCreateGoal:

    def test_valid_data_returns_201(self):
        """POST /v1/goals with valid data returns 201 with created goal."""
        row = _make_goal_row(name="Vacation", target_amount="5000.00")
        mock_conn, mock_cursor = _mock_conn(insert_row=row)

        with patch("src.savings_agent.handler.get_connection", return_value=mock_conn):
            resp = client.post(
                "/v1/goals",
                json={"name": "Vacation", "target_amount": "5000.00", "target_date": _FUTURE_DATE},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Vacation"
        assert Decimal(body["target_amount"]) == Decimal("5000.00")
        assert Decimal(body["current_amount"]) == Decimal("0.00")

    def test_past_target_date_returns_400(self):
        """POST /v1/goals with past target_date returns 400."""
        resp = client.post(
            "/v1/goals",
            json={"name": "Old Goal", "target_amount": "1000.00", "target_date": "2020-01-01"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"
        assert body["status"] == 400

    def test_today_as_target_date_returns_400(self):
        """POST /v1/goals with today as target_date returns 400 (must be strictly future)."""
        today = date.today().isoformat()
        resp = client.post(
            "/v1/goals",
            json={"name": "Today Goal", "target_amount": "1000.00", "target_date": today},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"

    def test_negative_target_amount_returns_400(self):
        """POST /v1/goals with negative target_amount returns 400."""
        resp = client.post(
            "/v1/goals",
            json={"name": "Bad Goal", "target_amount": "-500.00", "target_date": _FUTURE_DATE},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"

    def test_zero_target_amount_returns_400(self):
        """POST /v1/goals with zero target_amount returns 400."""
        resp = client.post(
            "/v1/goals",
            json={"name": "Zero Goal", "target_amount": "0", "target_date": _FUTURE_DATE},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"


# ---------------------------------------------------------------------------
# GET /v1/goals
# ---------------------------------------------------------------------------

class TestListGoals:

    def test_returns_goals_with_progress_fields(self):
        """GET /v1/goals returns goals with progress_pct and predicted_completion_date."""
        goal_row = _make_goal_row(name="Vacation", target_amount="5000.00", current_amount="0.00")
        mock_conn, mock_cursor = _mock_conn()

        # fetchall returns: goals, income_since_creation, expenses_since_creation,
        #                   all_income (monthly rate), all_expenses (monthly rate)
        mock_cursor.fetchall.side_effect = [
            [goal_row],   # goals query
            [(Decimal("1000.00"),)],  # income since creation
            [(Decimal("200.00"),)],   # expenses since creation
            [(Decimal("1000.00"), date.today() - timedelta(days=5))],  # all income (monthly rate)
            [(Decimal("200.00"), date.today() - timedelta(days=5))],   # all expenses (monthly rate)
        ]

        with patch("src.savings_agent.handler.get_connection", return_value=mock_conn):
            resp = client.get("/v1/goals")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        goal = body[0]
        assert "progress_pct" in goal
        assert "predicted_completion_date" in goal
        assert "current_amount" in goal
        assert "target_amount" in goal
        assert isinstance(goal["progress_pct"], float)

    def test_empty_goals_returns_200(self):
        """GET /v1/goals with no goals returns 200 with empty list."""
        mock_conn, mock_cursor = _mock_conn()
        mock_cursor.fetchall.return_value = []

        with patch("src.savings_agent.handler.get_connection", return_value=mock_conn):
            resp = client.get("/v1/goals")

        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Calculator: calculate_progress
# ---------------------------------------------------------------------------

class TestCalculateProgress:

    def test_income_greater_than_expenses_returns_positive(self):
        """calculate_progress returns positive when income > expenses."""
        income_rows = [(Decimal("1000.00"),), (Decimal("500.00"),)]
        expense_rows = [(Decimal("300.00"),), (Decimal("200.00"),)]
        result = calculate_progress(_NOW, income_rows, expense_rows)
        assert result == Decimal("1000.00")

    def test_expenses_greater_than_income_returns_negative(self):
        """calculate_progress returns negative when expenses > income."""
        income_rows = [(Decimal("200.00"),)]
        expense_rows = [(Decimal("500.00"),), (Decimal("300.00"),)]
        result = calculate_progress(_NOW, income_rows, expense_rows)
        assert result == Decimal("-600.00")

    def test_empty_rows_returns_zero(self):
        """calculate_progress with empty rows returns Decimal('0')."""
        result = calculate_progress(_NOW, [], [])
        assert result == Decimal("0")

    def test_only_income_no_expenses(self):
        """calculate_progress with only income returns total income."""
        income_rows = [(Decimal("750.00"),)]
        result = calculate_progress(_NOW, income_rows, [])
        assert result == Decimal("750.00")

    def test_only_expenses_no_income(self):
        """calculate_progress with only expenses returns negative total."""
        expense_rows = [(Decimal("400.00"),)]
        result = calculate_progress(_NOW, [], expense_rows)
        assert result == Decimal("-400.00")


# ---------------------------------------------------------------------------
# Calculator: predict_completion
# ---------------------------------------------------------------------------

class TestPredictCompletion:

    def test_positive_rate_returns_future_date(self):
        """predict_completion with positive monthly_rate returns a future date."""
        result = predict_completion(
            current_amount=Decimal("500.00"),
            target_amount=Decimal("5000.00"),
            monthly_rate=Decimal("450.00"),
        )
        assert result is not None
        assert result > date.today()

    def test_zero_rate_returns_none(self):
        """predict_completion with zero monthly_rate returns None."""
        result = predict_completion(
            current_amount=Decimal("500.00"),
            target_amount=Decimal("5000.00"),
            monthly_rate=Decimal("0"),
        )
        assert result is None

    def test_negative_rate_returns_none(self):
        """predict_completion with negative monthly_rate returns None."""
        result = predict_completion(
            current_amount=Decimal("500.00"),
            target_amount=Decimal("5000.00"),
            monthly_rate=Decimal("-100.00"),
        )
        assert result is None

    def test_already_reached_returns_today(self):
        """predict_completion when current_amount >= target_amount returns today."""
        result = predict_completion(
            current_amount=Decimal("5000.00"),
            target_amount=Decimal("5000.00"),
            monthly_rate=Decimal("500.00"),
        )
        assert result == date.today()

    def test_exceeded_target_returns_today(self):
        """predict_completion when current_amount > target_amount returns today."""
        result = predict_completion(
            current_amount=Decimal("6000.00"),
            target_amount=Decimal("5000.00"),
            monthly_rate=Decimal("500.00"),
        )
        assert result == date.today()
