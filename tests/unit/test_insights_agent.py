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
        """In ENVIRONMENT=local without CEREBRAS_API_KEY, returns deterministic answer."""
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
        assert len(body["answer"]) > 0


# ---------------------------------------------------------------------------
# Bedrock failure fallback
# ---------------------------------------------------------------------------

class TestBedrockFailureFallback:

    def test_llm_exception_returns_fallback_with_200(self):
        """LLM failure returns a valid answer (SQL fallback or message) with HTTP 200."""
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
        assert len(body["answer"]) > 0  # judge returns SQL fallback or fallback message

    def test_llm_empty_response_returns_fallback_with_200(self):
        """LLM returning empty string returns a valid answer with HTTP 200."""
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
        assert len(body["answer"]) > 0  # judge returns SQL fallback for spend queries


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

        assert ctx["total_income_90_days"] == 1500.0
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

        assert ctx["total_expenses_90_days"] == 350.0
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

        assert ctx["net_savings_90_days"] == pytest.approx(1800.0)
        assert ctx["period"] == "last 90 days"

    def test_context_period_is_last_90_days(self):
        """build_financial_context always sets period to 'last 90 days'."""
        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_cursor.fetchall.side_effect = [[], [], []]
        mock_conn.cursor.return_value = mock_cursor

        ctx = build_financial_context("user-1", mock_conn)

        assert ctx["period"] == "last 90 days"


# ---------------------------------------------------------------------------
# Validation Engine — 3 layers
# ---------------------------------------------------------------------------

class TestValidationEngine:
    """Tests for the 3-layer Validation Engine in judge.py."""

    def _ctx(self):
        return {
            "total_income_90_days": 3000.0,
            "total_expenses_90_days": 1200.0,
            "net_savings_90_days": 1800.0,
            "expenses_this_month": 400.0,
            "expenses_last_month": 320.0,
            "income_this_month": 1500.0,
            "income_last_month": 1500.0,
            "income_entries": [{"amount": 3000.0, "source": "Salary", "date": "2024-05-01"}],
            "expense_entries": [
                {"amount": 400.0, "merchant": "Whole Foods", "category": "Groceries", "date": "2024-05-10"},
                {"amount": 320.0, "merchant": "Uber", "category": "Transportation", "date": "2024-04-15"},
            ],
            "expenses_by_category": {"Groceries": 400.0, "Transportation": 320.0},
            "savings_goals": [
                {"name": "Vacation", "target_amount": 5000.0, "current_amount": 1000.0,
                 "target_date": "2025-12-31", "progress_pct": 20.0}
            ],
        }

    # Layer 1: Numeric grounding
    def test_grounded_numbers_pass(self):
        from src.insights_agent.judge import _validate_answer
        ctx = self._ctx()
        passed, reason = _validate_answer("How much did I spend?", "You spent $400.0 this month.", ctx)
        assert passed is True

    def test_ungrounded_number_fails(self):
        from src.insights_agent.judge import _validate_answer
        ctx = self._ctx()
        passed, reason = _validate_answer("How much did I spend?", "You spent $9999.99 this month.", ctx)
        assert passed is False
        assert reason == "numbers_ungrounded"

    def test_no_numbers_in_answer_passes_grounding(self):
        from src.insights_agent.judge import _validate_answer
        ctx = self._ctx()
        passed, reason = _validate_answer("Am I doing well?", "You are managing your finances well.", ctx)
        assert passed is True

    # Layer 2: Coverage check
    def test_category_question_without_category_in_answer_fails(self):
        from src.insights_agent.judge import _validate_answer
        ctx = self._ctx()
        passed, reason = _validate_answer(
            "What is my biggest expense category?",
            "You spent some money on various things.",
            ctx,
        )
        assert passed is False
        assert reason == "coverage_insufficient"

    def test_category_question_with_category_in_answer_passes(self):
        from src.insights_agent.judge import _validate_answer
        ctx = self._ctx()
        passed, reason = _validate_answer(
            "What is my biggest expense category?",
            "Your biggest expense category is Groceries at $400.0.",
            ctx,
        )
        assert passed is True

    def test_goal_question_without_goal_name_fails(self):
        from src.insights_agent.judge import _validate_answer
        ctx = self._ctx()
        passed, reason = _validate_answer(
            "Am I on track with my savings goal?",
            "You are making progress.",
            ctx,
        )
        assert passed is False
        assert reason == "coverage_insufficient"

    def test_goal_question_with_percentage_passes(self):
        from src.insights_agent.judge import _validate_answer
        ctx = self._ctx()
        passed, reason = _validate_answer(
            "Am I on track with my savings goal?",
            "Your Vacation goal is 20% complete.",
            ctx,
        )
        assert passed is True

    # Layer 3: Relevance check
    def test_deflection_answer_fails_relevance(self):
        from src.insights_agent.judge import _validate_answer
        ctx = self._ctx()
        passed, reason = _validate_answer(
            "How much did I spend?",
            "I don't have enough information to answer that.",
            ctx,
        )
        assert passed is False
        assert reason == "answer_not_relevant"

    def test_too_short_answer_fails_relevance(self):
        from src.insights_agent.judge import _validate_answer
        ctx = self._ctx()
        passed, reason = _validate_answer("How much did I spend?", "A lot.", ctx)
        assert passed is False
        assert reason == "answer_not_relevant"

    def test_substantive_answer_passes_relevance(self):
        from src.insights_agent.judge import _validate_answer
        ctx = self._ctx()
        passed, reason = _validate_answer(
            "How much did I spend?",
            "You spent $400.0 this month on Groceries and Transportation.",
            ctx,
        )
        assert passed is True


# ---------------------------------------------------------------------------
# Decision transparency in API response
# ---------------------------------------------------------------------------

class TestDecisionTransparency:

    def test_response_includes_decision_field(self):
        """API response includes decision field for transparency."""
        mock_conn, _ = _make_mock_conn(
            income_rows=[_income_row()],
            expense_rows=[_expense_row()],
            goal_rows=[],
        )

        with patch("src.insights_agent.handler.get_connection", return_value=mock_conn):
            resp = client.post("/v1/insights/query", json={"question": "How much did I spend?"})

        assert resp.status_code == 200
        body = resp.json()
        assert "decision" in body
        assert body["decision"] in ("accept", "retry", "fallback", "sql_local", None)

    def test_local_mode_returns_sql_local_decision(self):
        """In local mode without API key, decision is sql_local."""
        mock_conn, _ = _make_mock_conn(
            income_rows=[_income_row()],
            expense_rows=[_expense_row("300.00", "Uber", "Transportation")],
            goal_rows=[],
        )

        with patch("src.insights_agent.handler.get_connection", return_value=mock_conn), \
             patch.dict(os.environ, {"ENVIRONMENT": "local", "CEREBRAS_API_KEY": ""}):
            resp = client.post("/v1/insights/query", json={"question": "How much did I spend last month?"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] == "sql_local"


# ---------------------------------------------------------------------------
# Coordinator pattern — worker contracts
# ---------------------------------------------------------------------------

class TestCoordinatorPattern:
    """Tests for the Coordinator–Worker pattern in context_builder."""

    def test_build_context_returns_data_sources(self):
        """build_financial_context includes data_sources tracking which agents contributed."""
        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_cursor.fetchall.side_effect = [
            [_income_row("1000.00")],   # income worker
            [_expense_row("200.00")],   # expense worker
            [_goal_row()],              # savings worker
        ]
        mock_conn.cursor.return_value = mock_cursor

        ctx = build_financial_context("user-1", mock_conn)

        assert "data_sources" in ctx
        assert "income_agent" in ctx["data_sources"]
        assert "expense_agent" in ctx["data_sources"]
        assert "savings_agent" in ctx["data_sources"]

    def test_empty_income_not_in_data_sources(self):
        """data_sources excludes agents that returned no data."""
        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_cursor.fetchall.side_effect = [
            [],                         # income worker — empty
            [_expense_row("200.00")],   # expense worker
            [],                         # savings worker — empty
        ]
        mock_conn.cursor.return_value = mock_cursor

        ctx = build_financial_context("user-1", mock_conn)

        assert "income_agent" not in ctx["data_sources"]
        assert "expense_agent" in ctx["data_sources"]
        assert "savings_agent" not in ctx["data_sources"]

    def test_income_worker_contract_structure(self):
        """fetch_income_context returns validated IncomeAgentContract."""
        from src.insights_agent.context_builder import fetch_income_context
        from src.insights_agent.models import IncomeAgentContract
        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_cursor.fetchall.return_value = [_income_row("2000.00", "Salary")]
        mock_conn.cursor.return_value = mock_cursor

        result = fetch_income_context("user-1", mock_conn)

        assert isinstance(result, IncomeAgentContract)
        assert result.agent == "income_agent"
        assert result.total_income_90_days == 2000.0
        assert len(result.entries) == 1
        assert result.entries[0].source == "Salary"
        assert result.fetched_at is not None

    def test_expense_worker_contract_structure(self):
        """fetch_expense_context returns validated ExpenseAgentContract with by_category."""
        from src.insights_agent.context_builder import fetch_expense_context
        from src.insights_agent.models import ExpenseAgentContract
        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_cursor.fetchall.return_value = [
            _expense_row("100.00", "Uber", "Transportation"),
            _expense_row("200.00", "Whole Foods", "Groceries"),
        ]
        mock_conn.cursor.return_value = mock_cursor

        result = fetch_expense_context("user-1", mock_conn)

        assert isinstance(result, ExpenseAgentContract)
        assert result.agent == "expense_agent"
        assert result.total_expenses_90_days == 300.0
        assert result.by_category["Transportation"] == 100.0
        assert result.by_category["Groceries"] == 200.0

    def test_savings_worker_contract_structure(self):
        """fetch_savings_context returns validated SavingsAgentContract with progress_pct."""
        from src.insights_agent.context_builder import fetch_savings_context
        from src.insights_agent.models import SavingsAgentContract
        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_cursor.fetchall.return_value = [_goal_row("Vacation", "5000.00", "1000.00")]
        mock_conn.cursor.return_value = mock_cursor

        result = fetch_savings_context("user-1", mock_conn)

        assert isinstance(result, SavingsAgentContract)
        assert result.agent == "savings_agent"
        assert len(result.goals) == 1
        assert result.goals[0].progress_pct == 20.0
        assert result.fetched_at is not None

    def test_coordinator_merges_all_worker_outputs(self):
        """build_financial_context merges all worker contracts into unified context."""
        mock_conn, mock_cursor = MagicMock(), MagicMock()
        mock_cursor.fetchall.side_effect = [
            [_income_row("3000.00")],
            [_expense_row("1200.00", "Uber", "Transportation")],
            [_goal_row("Vacation", "5000.00", "500.00")],
        ]
        mock_conn.cursor.return_value = mock_cursor

        ctx = build_financial_context("user-1", mock_conn)

        # Income fields present
        assert ctx["total_income_90_days"] == 3000.0
        # Expense fields present
        assert ctx["total_expenses_90_days"] == 1200.0
        assert "Transportation" in ctx["expenses_by_category"]
        # Savings fields present
        assert len(ctx["savings_goals"]) == 1
        # Derived
        assert ctx["net_savings_90_days"] == pytest.approx(1800.0)


# ---------------------------------------------------------------------------
# Validation Engine — Layer 4: Consistency check
# ---------------------------------------------------------------------------

class TestConsistencyCheck:

    def _ctx(self):
        return {
            "total_income_90_days": 3000.0,
            "total_expenses_90_days": 1200.0,
            "net_savings_90_days": 1800.0,
            "expenses_this_month": 400.0,
            "expenses_last_month": 320.0,
            "income_this_month": 1500.0,
            "income_last_month": 1500.0,
            "income_entries": [],
            "expense_entries": [],
            "expenses_by_category": {"Groceries": 400.0},
            "savings_goals": [],
        }

    def test_consistent_answer_passes(self):
        from src.insights_agent.judge import _validate_answer
        ctx = self._ctx()
        passed, reason = _validate_answer(
            "How much did I spend?",
            "You spent $400.0 this month on Groceries.",
            ctx,
        )
        assert passed is True

    def test_self_contradicting_higher_than_fails(self):
        from src.insights_agent.judge import _consistency_check
        ctx = self._ctx()
        # "$500 is higher than your total of $400" — 500 > 400 so "higher" is correct, should pass
        # "$300 is higher than your total of $400" — 300 > 400 is FALSE, should fail
        result = _consistency_check("$300 is higher than your total of $400.", ctx)
        assert result is False

    def test_non_contradicting_answer_passes_consistency(self):
        from src.insights_agent.judge import _consistency_check
        ctx = self._ctx()
        result = _consistency_check("You spent $400.0 this month.", ctx)
        assert result is True

    def test_api_response_includes_data_sources(self):
        """API response includes data_sources field."""
        mock_conn, _ = _make_mock_conn(
            income_rows=[_income_row()],
            expense_rows=[_expense_row()],
            goal_rows=[],
        )

        with patch("src.insights_agent.handler.get_connection", return_value=mock_conn):
            resp = client.post("/v1/insights/query", json={"question": "How much did I spend?"})

        assert resp.status_code == 200
        body = resp.json()
        assert "data_sources" in body
        assert isinstance(body["data_sources"], list)


# ---------------------------------------------------------------------------
# OrchestrationState + trace_id
# ---------------------------------------------------------------------------

class TestOrchestrationState:

    def test_state_has_trace_id(self):
        """OrchestrationState generates a unique trace_id."""
        from src.insights_agent.models import OrchestrationState
        s1 = OrchestrationState(user_id="u1", question="q")
        s2 = OrchestrationState(user_id="u1", question="q")
        assert s1.trace_id != s2.trace_id
        assert len(s1.trace_id) == 36  # UUID format

    def test_state_finish_sets_decision(self):
        """OrchestrationState.finish() sets decision, reason, and completed_at."""
        from src.insights_agent.models import OrchestrationState
        state = OrchestrationState(user_id="u1", question="q")
        state.finish("accept", "numbers_verified")
        assert state.decision == "accept"
        assert state.reason == "numbers_verified"
        assert state.completed_at is not None

    def test_state_tracks_data_sources(self):
        """OrchestrationState tracks which agents contributed data."""
        from src.insights_agent.models import OrchestrationState
        state = OrchestrationState(user_id="u1", question="q")
        state.data_sources = ["income_agent", "expense_agent"]
        assert "income_agent" in state.data_sources
        assert "savings_agent" not in state.data_sources

    def test_api_response_includes_trace_id(self):
        """API response includes trace_id field."""
        mock_conn, _ = _make_mock_conn(
            income_rows=[_income_row()],
            expense_rows=[_expense_row()],
            goal_rows=[],
        )
        with patch("src.insights_agent.handler.get_connection", return_value=mock_conn):
            resp = client.post("/v1/insights/query", json={"question": "How much did I spend?"})

        assert resp.status_code == 200
        body = resp.json()
        assert "trace_id" in body
        assert body["trace_id"] is not None
        assert len(body["trace_id"]) == 36


# ---------------------------------------------------------------------------
# LLM output schema validation
# ---------------------------------------------------------------------------

class TestLlmOutputSchemaValidation:

    def test_empty_output_rejected(self):
        from src.insights_agent.judge import _validate_llm_output
        valid, reason = _validate_llm_output("")
        assert valid is False
        assert reason == "empty_output"

    def test_whitespace_only_rejected(self):
        from src.insights_agent.judge import _validate_llm_output
        valid, reason = _validate_llm_output("   ")
        assert valid is False
        assert reason == "empty_output"

    def test_json_output_rejected(self):
        from src.insights_agent.judge import _validate_llm_output
        valid, reason = _validate_llm_output('{"answer": "You spent $400"}')
        assert valid is False
        assert reason == "output_is_json_not_prose"

    def test_too_long_output_rejected(self):
        from src.insights_agent.judge import _validate_llm_output, MAX_ANSWER_TOKENS
        long_text = " ".join(["word"] * (MAX_ANSWER_TOKENS + 1))
        valid, reason = _validate_llm_output(long_text)
        assert valid is False
        assert reason == "output_too_long"

    def test_valid_prose_accepted(self):
        from src.insights_agent.judge import _validate_llm_output
        valid, reason = _validate_llm_output("You spent $400 this month on Groceries.")
        assert valid is True
        assert reason == "ok"


# ---------------------------------------------------------------------------
# Guardrail constants
# ---------------------------------------------------------------------------

class TestGuardrailConstants:

    def test_max_retries_is_one(self):
        from src.insights_agent.judge import MAX_RETRIES
        assert MAX_RETRIES == 1

    def test_cost_limit_defined(self):
        from src.insights_agent.judge import COST_LIMIT_USD
        assert COST_LIMIT_USD > 0

    def test_latency_limit_defined(self):
        from src.insights_agent.judge import LATENCY_LIMIT_MS
        assert LATENCY_LIMIT_MS > 0

    def test_llm_timeout_defined(self):
        from src.insights_agent.judge import LLM_TIMEOUT_S
        assert LLM_TIMEOUT_S > 0
