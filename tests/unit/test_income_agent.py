"""Unit tests for the Income Agent Lambda handler."""
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

from src.income_agent.handler import app

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
    amount="500.00",
    source="Salary",
    entry_date=None,
    notes=None,
    created_at=None,
):
    return (
        entry_id or uuid4(),
        user_id or uuid4(),
        Decimal(amount),
        source,
        entry_date or date(2024, 1, 10),
        notes,
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
# POST /v1/income
# ---------------------------------------------------------------------------

class TestCreateIncome:

    def test_valid_data_returns_201(self):
        row = _make_row(amount="1500.00", source="Salary", entry_date=date(2024, 1, 10))
        mock_conn, mock_cursor = _mock_conn(insert_row=row)
        mock_cursor.fetchone.return_value = row

        with patch("src.income_agent.handler.get_connection", return_value=mock_conn):
            resp = client.post(
                "/v1/income",
                json={"amount": "1500.00", "source": "Salary", "date": "2024-01-10"},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["source"] == "Salary"
        assert Decimal(body["amount"]) == Decimal("1500.00")

    def test_amount_zero_returns_400(self):
        resp = client.post(
            "/v1/income",
            json={"amount": "0", "source": "Salary", "date": "2024-01-10"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"
        assert body["status"] == 400

    def test_negative_amount_returns_400(self):
        resp = client.post(
            "/v1/income",
            json={"amount": "-100", "source": "Salary", "date": "2024-01-10"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"

    def test_future_date_returns_400(self):
        resp = client.post(
            "/v1/income",
            json={"amount": "500", "source": "Freelance", "date": "2099-12-31"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "validation_error"

    def test_missing_required_fields_returns_400(self):
        # Missing 'source' and 'date'
        resp = client.post("/v1/income", json={"amount": "500"})
        assert resp.status_code == 400

    def test_missing_amount_returns_400(self):
        resp = client.post(
            "/v1/income",
            json={"source": "Salary", "date": "2024-01-10"},
        )
        assert resp.status_code == 400

    def test_invalid_date_format_returns_400(self):
        resp = client.post(
            "/v1/income",
            json={"amount": "500", "source": "Salary", "date": "not-a-date"},
        )
        assert resp.status_code == 400

    def test_optional_notes_accepted(self):
        row = _make_row(amount="200.00", source="Bonus", notes="Q4 bonus")
        mock_conn, mock_cursor = _mock_conn(insert_row=row)
        mock_cursor.fetchone.return_value = row

        with patch("src.income_agent.handler.get_connection", return_value=mock_conn):
            resp = client.post(
                "/v1/income",
                json={
                    "amount": "200.00",
                    "source": "Bonus",
                    "date": "2024-01-05",
                    "notes": "Q4 bonus",
                },
            )

        assert resp.status_code == 201
        assert resp.json()["notes"] == "Q4 bonus"


# ---------------------------------------------------------------------------
# GET /v1/income
# ---------------------------------------------------------------------------

class TestListIncome:

    def test_returns_200_with_entries(self):
        rows = [
            _make_row(amount="1000.00", source="Salary", entry_date=date(2024, 1, 15)),
            _make_row(amount="500.00", source="Freelance", entry_date=date(2024, 1, 10)),
            _make_row(amount="200.00", source="Bonus", entry_date=date(2024, 1, 5)),
        ]
        mock_conn, mock_cursor = _mock_conn(rows=rows)
        mock_cursor.fetchall.return_value = rows

        with patch("src.income_agent.handler.get_connection", return_value=mock_conn):
            resp = client.get("/v1/income")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 3

    def test_entries_sorted_by_date_desc(self):
        rows = [
            _make_row(amount="1000.00", source="Salary", entry_date=date(2024, 1, 15)),
            _make_row(amount="500.00", source="Freelance", entry_date=date(2024, 1, 10)),
            _make_row(amount="200.00", source="Bonus", entry_date=date(2024, 1, 5)),
        ]
        mock_conn, mock_cursor = _mock_conn(rows=rows)
        mock_cursor.fetchall.return_value = rows

        with patch("src.income_agent.handler.get_connection", return_value=mock_conn):
            resp = client.get("/v1/income")

        body = resp.json()
        dates = [entry["date"] for entry in body]
        assert dates == sorted(dates, reverse=True), "Entries must be sorted by date DESC"

    def test_empty_list_returns_200(self):
        mock_conn, mock_cursor = _mock_conn(rows=[])
        mock_cursor.fetchall.return_value = []

        with patch("src.income_agent.handler.get_connection", return_value=mock_conn):
            resp = client.get("/v1/income")

        assert resp.status_code == 200
        assert resp.json() == []
