"""Unit tests for the Insights Agent Lambda handler."""
import json
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

# Set ENVIRONMENT=local before importing the app so auth is bypassed and Bedrock is skipped
os.environ.setdefault("ENVIRONMENT", "local")

from src.insights_agent.handler import app
from src.insights_agent.context_builder import build_financial_context

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = str(uuid4())
_NOW = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)


def _make_mock_conn(income_rows=None, expense_rows=None, goal_rows=None):
    """Return a mock psycopg2 connection with preset query results."""
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)

    # fetchall cycles through: income, expenses, goals
    mock_cursor.fetchall.side_effect = [
        income_rows or [],
        expense_rows or [],
        goal_rows or [],
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


def _income_row(amount="1000.00", source="Salary", entry_date=None):
    return (Decimal(amount), source, entry_date or date(2024, 5, 1))


def _expense_row(amount="200.00", merchant="Uber", category="Transportation", entry_date=None):
    return (Decimal(amount), merchant, category, entry_date or date(2024, 5, 10))


def _goal_row(name="Vacation", target="5000.00", current="1000.00", target_date=None):
    return (name, Decimal(target), Decimal(current), target_date or date(2025, 12, 31))


# ---------------------------------------------------------------------------
# POST /v1/insights/query — basic cases
# ---------------------------------------------------------------------------

class TestQueryInsights:

    def test_valid_question_returns_200_with_answer(self):
        """POST /v1/insights/query with valid question returns 200 with answer."""
        mock_conn, _ = _make_mock_conn(
            income_rows=[_income_row()],
            expense_rows=[_expense_row()],
            goal_rows=[_goal_row()],
        )

        with patch("src.insights_agent.handler.get_connection", return_value=mock_conn):
            resp = client.post("/v1/insights/query", json={"question": "How much did I spend?"})

        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body
        assert "query" in body
        assert "generated_at" in body
        assert body["query"] == "How much did I spend?"
        assert len(body["answer"]) > 0

    def test_empty_question_returns_400(self):
        """POST /v1/insights/query with empty question returns 400."""
        resp = client.post("/v1/insights/query", json={"question": ""})
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"
        assert body["status"] == 400

    def test_whitespace_only_question_returns_400(self):
        """POST /v1/insights/query with whitespace-only question returns 400."""
        resp = client.post("/v1/insights/query", json={"question": "   "})
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"

    def test_missing_question_field_returns_400(self):
        """POST /v1/insights/query with missing question field returns 400."""
        resp = client.post("/v1/insights/query", json={})
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"

    def test_no_financial_data_returns_helpful_message(self):
        """POST /v1/insights/query with no data returns helpful no-data message with 200."""
        mock_conn, _ = _make_mock_conn(
            income_rows=[],
            expense_rows=[],
            goal_rows=[],
        )

        with patch("src.insights_agent.handler.get_connection", return_value=mock_conn):
            resp = client.post("/v1/insights/query", json={"question": "How am I doing?"})

        assert resp.status_code == 200
        body = resp.json()
        assert "No financial data found" in body["answer"]
        assert "income or expense" in body["answer"]

    def test_local_dev_returns_mock_answer_without_bedrock(self):
        """In ENVIRONMENT=local without CEREBRAS_API_KEY, returns rule-based answer."""
        mock_conn, _ = _make_mock_conn(
            income_rows=[_income_row("2000.00"), _income_row("500.00")],
            expense_rows=[_expense_row("300.00"), _expense_row("150.00")],
            goal_rows=[],
        )

        with patch("src.insights_agent.handler.get_connection", return_value=mock_conn), \
             patch.dict(os.environ, {"ENVIRONMENT": "local", "CEREBRAS_API_KEY": ""}):
            resp = client.post("/v1/insights/query", json={"question": "What is my net savings?"})

        assert resp.status_code == 200
        body = resp.json()
        assert "income" in body["answer"].lower() or "2500" in body["answer"]


# ---------------------------------------------------------------------------
# Bedrock failure fallback
# ---------------------------------------------------------------------------

class TestBedrockFailureFallback:

    def test_llm_exception_returns_fallback_with_200(self):
        """LLM failure returns fallback message with HTTP 200 (not 500)."""
        mock_conn, _ = _make_mock_conn(
            income_rows=[_income_row()],
            expense_rows=[_expense_row()],
            goal_rows=[],
        )

        with patch.dict(os.environ, {"ENVIRONMENT": "production", "CEREBRAS_API_KEY": "test-key"}), \
             patch("src.insights_agent.handler.get_connection", return_value=mock_conn), \
             patch("src.insights_agent.handler.get_user_id_from_event", return_value="test-user"), \
             patch("src.shared.llm.call_llm", side_effect=Exception("LLM error")):
            resp = client.post("/v1/insights/query", json={"question": "How much did I spend?"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"] == "I was unable to process your query at this time. Please try again."

    def test_llm_empty_response_returns_fallback_with_200(self):
        """LLM returning empty string returns fallback message with HTTP 200."""
        mock_conn, _ = _make_mock_conn(
            income_rows=[_income_row()],
            expense_rows=[_expense_row()],
            goal_rows=[],
        )

        with patch.dict(os.environ, {"ENVIRONMENT": "production", "CEREBRAS_API_KEY": "test-key"}), \
             patch("src.insights_agent.handler.get_connection", return_value=mock_conn), \
             patch("src.insights_agent.handler.get_user_id_from_event", return_value="test-user"), \
             patch("src.shared.llm.call_llm", return_value=""):
            resp = client.post("/v1/insights/query", json={"question": "How much did I spend?"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"] == "I was unable to process your query at this time. Please try again."


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

class TestContextAssembly:

    def test_context_includes_income_totals(self):
        """build_financial_context includes correct total_income."""
        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_cursor.fetchall.side_effect = [
            [_income_row("1000.00"), _income_row("500.00")],  # income
            [],  # expenses
            [],  # goals
        ]
        mock_conn.cursor.return_value = mock_cursor

        ctx = build_financial_context("user-1", mock_conn)

        assert ctx["total_income"] == 1500.0
        assert len(ctx["income_entries"]) == 2

    def test_context_includes_expense_totals_by_category(self):
        """build_financial_context includes expenses_by_category aggregation."""
        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_cursor.fetchall.side_effect = [
            [],  # income
            [
                _expense_row("100.00", "Uber", "Transportation"),
                _expense_row("50.00", "Lyft", "Transportation"),
                _expense_row("200.00", "Whole Foods", "Groceries"),
            ],
            [],  # goals
        ]
        mock_conn.cursor.return_value = mock_cursor

        ctx = build_financial_context("user-1", mock_conn)

        assert ctx["total_expenses"] == 350.0
        assert ctx["expenses_by_category"]["Transportation"] == 150.0
        assert ctx["expenses_by_category"]["Groceries"] == 200.0

    def test_context_includes_savings_goals_with_progress(self):
        """build_financial_context includes savings goals with progress_pct."""
        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_cursor.fetchall.side_effect = [
            [],  # income
            [],  # expenses
            [_goal_row("Vacation", "5000.00", "1000.00")],
        ]
        mock_conn.cursor.return_value = mock_cursor

        ctx = build_financial_context("user-1", mock_conn)

        assert len(ctx["savings_goals"]) == 1
        goal = ctx["savings_goals"][0]
        assert goal["name"] == "Vacation"
        assert goal["target_amount"] == 5000.0
        assert goal["current_amount"] == 1000.0
        assert goal["progress_pct"] == 20.0

    def test_context_net_savings_calculation(self):
        """build_financial_context computes net_savings = total_income - total_expenses."""
        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_cursor.fetchall.side_effect = [
            [_income_row("3000.00")],
            [_expense_row("1200.00")],
            [],
        ]
        mock_conn.cursor.return_value = mock_cursor

        ctx = build_financial_context("user-1", mock_conn)

        assert ctx["net_savings"] == pytest.approx(1800.0)
        assert ctx["period"] == "last 90 days"

    def test_context_period_is_last_90_days(self):
        """build_financial_context always sets period to 'last 90 days'."""
        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_cursor.fetchall.side_effect = [[], [], []]
        mock_conn.cursor.return_value = mock_cursor

        ctx = build_financial_context("user-1", mock_conn)

        assert ctx["period"] == "last 90 days"
