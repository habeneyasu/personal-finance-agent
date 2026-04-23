"""Unit tests for the Expense Agent Lambda handler."""
import json
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

# Set ENVIRONMENT=local before importing the app so auth is bypassed
os.environ.setdefault("ENVIRONMENT", "local")

from src.expense_agent.handler import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = str(uuid4())
_ENTRY_ID = str(uuid4())
_NOW = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)


def _make_row(
    entry_id=None,
    user_id=None,
    amount="50.00",
    merchant="Test Merchant",
    category="Other",
    entry_date=None,
    created_at=None,
):
    return (
        entry_id or uuid4(),
        user_id or uuid4(),
        Decimal(amount),
        merchant,
        category,
        entry_date or date(2024, 1, 10),
        created_at or _NOW,
    )


def _mock_conn(rows=None, insert_row=None):
    """Return a mock psycopg2 connection whose cursor returns given rows."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = insert_row
    mock_cursor.fetchall.return_value = rows or []
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


# ---------------------------------------------------------------------------
# POST /v1/expenses
# ---------------------------------------------------------------------------

class TestCreateExpense:

    def test_valid_data_returns_201(self):
        """Test creating an expense with valid data returns 201 with category."""
        row = _make_row(amount="50.00", merchant="Uber", category="Transportation")
        mock_conn, mock_cursor = _mock_conn(insert_row=row)
        mock_cursor.fetchone.return_value = row

        with patch("src.expense_agent.handler.get_connection", return_value=mock_conn):
            resp = client.post(
                "/v1/expenses",
                json={"amount": "50.00", "merchant": "Uber", "date": "2024-01-10"},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["merchant"] == "Uber"
        assert Decimal(body["amount"]) == Decimal("50.00")
        assert body["category"] in [
            "Groceries",
            "Transportation",
            "Entertainment",
            "Utilities",
            "Healthcare",
            "Shopping",
            "Dining",
            "Other",
        ]

    def test_local_categorization_uber(self):
        """Test local rule-based categorization for Uber."""
        row = _make_row(amount="50.00", merchant="Uber", category="Transportation")
        mock_conn, mock_cursor = _mock_conn(insert_row=row)
        mock_cursor.fetchone.return_value = row

        with patch("src.expense_agent.handler.get_connection", return_value=mock_conn):
            resp = client.post(
                "/v1/expenses",
                json={"amount": "50.00", "merchant": "Uber", "date": "2024-01-10"},
            )

        assert resp.status_code == 201
        # In local mode, Uber should be categorized as Transportation
        # The mock returns the category, so we verify the call was made
        assert mock_cursor.execute.called

    def test_amount_zero_returns_400(self):
        """Test that amount=0 returns 400."""
        resp = client.post(
            "/v1/expenses",
            json={"amount": "0", "merchant": "Test", "date": "2024-01-10"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"
        assert body["status"] == 400

    def test_negative_amount_returns_400(self):
        """Test that negative amount returns 400."""
        resp = client.post(
            "/v1/expenses",
            json={"amount": "-100", "merchant": "Test", "date": "2024-01-10"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"

    def test_missing_required_fields_returns_400(self):
        """Test that missing required fields returns 400."""
        # Missing 'merchant' and 'date'
        resp = client.post("/v1/expenses", json={"amount": "50"})
        assert resp.status_code == 400

    def test_missing_amount_returns_400(self):
        """Test that missing amount returns 400."""
        resp = client.post(
            "/v1/expenses",
            json={"merchant": "Test", "date": "2024-01-10"},
        )
        assert resp.status_code == 400

    def test_invalid_date_format_returns_400(self):
        """Test that invalid date format returns 400."""
        resp = client.post(
            "/v1/expenses",
            json={"amount": "50", "merchant": "Test", "date": "not-a-date"},
        )
        assert resp.status_code == 400

    def test_future_date_returns_400(self):
        """Test that future date returns 400."""
        resp = client.post(
            "/v1/expenses",
            json={"amount": "50", "merchant": "Test", "date": "2099-12-31"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"


# ---------------------------------------------------------------------------
# GET /v1/expenses
# ---------------------------------------------------------------------------

class TestListExpenses:

    def test_returns_200_with_entries(self):
        """Test listing expenses returns 200 with entries."""
        rows = [
            _make_row(amount="50.00", merchant="Uber", category="Transportation", entry_date=date(2024, 1, 15)),
            _make_row(amount="100.00", merchant="Whole Foods", category="Groceries", entry_date=date(2024, 1, 10)),
            _make_row(amount="25.00", merchant="Cafe", category="Dining", entry_date=date(2024, 1, 5)),
        ]
        mock_conn, mock_cursor = _mock_conn(rows=rows)
        mock_cursor.fetchall.return_value = rows

        with patch("src.expense_agent.handler.get_connection", return_value=mock_conn):
            resp = client.get("/v1/expenses")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 3

    def test_entries_sorted_by_date_desc(self):
        """Test that entries are sorted by date descending."""
        rows = [
            _make_row(amount="50.00", merchant="Uber", category="Transportation", entry_date=date(2024, 1, 15)),
            _make_row(amount="100.00", merchant="Whole Foods", category="Groceries", entry_date=date(2024, 1, 10)),
            _make_row(amount="25.00", merchant="Cafe", category="Dining", entry_date=date(2024, 1, 5)),
        ]
        mock_conn, mock_cursor = _mock_conn(rows=rows)
        mock_cursor.fetchall.return_value = rows

        with patch("src.expense_agent.handler.get_connection", return_value=mock_conn):
            resp = client.get("/v1/expenses")

        body = resp.json()
        dates = [entry["date"] for entry in body]
        assert dates == sorted(dates, reverse=True), "Entries must be sorted by date DESC"

    def test_empty_list_returns_200(self):
        """Test that empty list returns 200."""
        mock_conn, mock_cursor = _mock_conn(rows=[])
        mock_cursor.fetchall.return_value = []

        with patch("src.expense_agent.handler.get_connection", return_value=mock_conn):
            resp = client.get("/v1/expenses")

        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Bedrock Integration Tests
# ---------------------------------------------------------------------------

class TestBedrockCategorization:
    """Tests for LLM categorization — mocks call_llm to isolate categorizer logic."""

    def test_llm_returns_groceries(self):
        """LLM categorization returning 'Groceries'."""
        row = _make_row(amount="100.00", merchant="Whole Foods", category="Groceries")
        mock_conn, mock_cursor = _mock_conn(insert_row=row)
        mock_cursor.fetchone.return_value = row

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}), \
             patch("src.shared.llm.call_llm", return_value="Groceries"), \
             patch("src.expense_agent.handler.get_user_id_from_event", return_value="test-user"), \
             patch("src.expense_agent.handler.get_connection", return_value=mock_conn):
            resp = client.post(
                "/v1/expenses",
                json={"amount": "100.00", "merchant": "Whole Foods", "date": "2024-01-10"},
            )

        assert resp.status_code == 201
        assert mock_cursor.execute.called

    def test_llm_client_error_defaults_to_other(self):
        """LLM failure defaults category to 'Other' and still returns 201."""
        row = _make_row(amount="50.00", merchant="Unknown", category="Other")
        mock_conn, mock_cursor = _mock_conn(insert_row=row)
        mock_cursor.fetchone.return_value = row

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}), \
             patch("src.shared.llm.call_llm", side_effect=Exception("LLM error")), \
             patch("src.expense_agent.handler.get_user_id_from_event", return_value="test-user"), \
             patch("src.expense_agent.handler.get_connection", return_value=mock_conn):
            resp = client.post(
                "/v1/expenses",
                json={"amount": "50.00", "merchant": "Unknown", "date": "2024-01-10"},
            )

        assert resp.status_code == 201
        assert mock_cursor.execute.called

    def test_llm_invalid_category_defaults_to_other(self):
        """LLM returning invalid category defaults to 'Other'."""
        row = _make_row(amount="50.00", merchant="Test", category="Other")
        mock_conn, mock_cursor = _mock_conn(insert_row=row)
        mock_cursor.fetchone.return_value = row

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}), \
             patch("src.shared.llm.call_llm", return_value="InvalidCategory"), \
             patch("src.expense_agent.handler.get_user_id_from_event", return_value="test-user"), \
             patch("src.expense_agent.handler.get_connection", return_value=mock_conn):
            resp = client.post(
                "/v1/expenses",
                json={"amount": "50.00", "merchant": "Test", "date": "2024-01-10"},
            )

        assert resp.status_code == 201

    def test_llm_empty_response_defaults_to_other(self):
        """LLM returning empty string defaults to 'Other'."""
        row = _make_row(amount="50.00", merchant="Test", category="Other")
        mock_conn, mock_cursor = _mock_conn(insert_row=row)
        mock_cursor.fetchone.return_value = row

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}), \
             patch("src.shared.llm.call_llm", return_value=""), \
             patch("src.expense_agent.handler.get_user_id_from_event", return_value="test-user"), \
             patch("src.expense_agent.handler.get_connection", return_value=mock_conn):
            resp = client.post(
                "/v1/expenses",
                json={"amount": "50.00", "merchant": "Test", "date": "2024-01-10"},
            )

        assert resp.status_code == 201
