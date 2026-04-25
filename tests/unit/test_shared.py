"""Unit tests for src/shared — logger, exceptions, and validators."""
import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.shared.exceptions import handle_unhandled_exception
from src.shared.validation import (
    validate_goal_target_date,
    validate_income_date,
    validate_iso_date,
    validate_positive_amount,
)


# ---------------------------------------------------------------------------
# Logger tests
# ---------------------------------------------------------------------------

class TestLogger:
    """Tests that the Logger emits the required structured fields."""

    def test_logger_info_emits_required_fields(self, caplog):
        """Logger.info should produce a record with user_id, operation, status."""
        from src.shared.logger import Logger

        logger = Logger(service="test-service")

        with caplog.at_level(logging.INFO):
            with patch.object(logger._logger, "info") as mock_info:
                logger.info(
                    "test message",
                    user_id="user-123",
                    operation="create_income",
                    status="ok",
                )
                mock_info.assert_called_once()
                _, kwargs = mock_info.call_args
                extra = kwargs.get("extra", {})
                assert extra["user_id"] == "user-123"
                assert extra["operation"] == "create_income"
                assert extra["status"] == "ok"

    def test_logger_error_emits_required_fields(self):
        """Logger.error should include user_id, operation, status='error'."""
        from src.shared.logger import Logger

        logger = Logger(service="test-service")

        with patch.object(logger._logger, "error") as mock_error:
            logger.error(
                "something failed",
                user_id="user-456",
                operation="list_expenses",
                status="error",
            )
            mock_error.assert_called_once()
            _, kwargs = mock_error.call_args
            extra = kwargs.get("extra", {})
            assert extra["user_id"] == "user-456"
            assert extra["operation"] == "list_expenses"
            assert extra["status"] == "error"

    def test_logger_exception_emits_required_fields(self):
        """Logger.exception should include user_id, operation, status fields."""
        from src.shared.logger import Logger

        logger = Logger(service="test-service")

        with patch.object(logger._logger, "exception") as mock_exc:
            logger.exception(
                "unhandled error",
                user_id="user-789",
                operation="create_goal",
                status="error",
            )
            mock_exc.assert_called_once()
            _, kwargs = mock_exc.call_args
            extra = kwargs.get("extra", {})
            assert extra["user_id"] == "user-789"
            assert extra["operation"] == "create_goal"
            assert extra["status"] == "error"

    def test_logger_default_status_is_ok(self):
        """Logger.info default status should be 'ok'."""
        from src.shared.logger import Logger

        logger = Logger(service="test-service")

        with patch.object(logger._logger, "info") as mock_info:
            logger.info("msg", user_id="u1", operation="op1")
            _, kwargs = mock_info.call_args
            assert kwargs["extra"]["status"] == "ok"


# ---------------------------------------------------------------------------
# handle_unhandled_exception decorator tests
# ---------------------------------------------------------------------------

class TestHandleUnhandledException:
    """Tests for the handle_unhandled_exception decorator."""

    def _make_context(self, request_id: str = "req-abc-123"):
        ctx = MagicMock()
        ctx.aws_request_id = request_id
        return ctx

    def test_returns_http_500_on_exception(self):
        """Decorator should return statusCode 500 when handler raises."""

        @handle_unhandled_exception
        def bad_handler(event, context):
            raise RuntimeError("boom")

        response = bad_handler({}, self._make_context())
        assert response["statusCode"] == 500

    def test_response_body_has_correct_shape(self):
        """Response body must contain error, request_id, and status fields."""

        @handle_unhandled_exception
        def bad_handler(event, context):
            raise ValueError("bad input")

        ctx = self._make_context("req-xyz-999")
        response = bad_handler({}, ctx)
        body = json.loads(response["body"])

        assert body["error"] == "internal_server_error"
        assert body["request_id"] == "req-xyz-999"
        assert body["status"] == 500

    def test_logs_traceback_on_exception(self):
        """Decorator should call logger.exception (which logs the traceback)."""

        @handle_unhandled_exception
        def bad_handler(event, context):
            raise TypeError("type error")

        with patch("src.shared.exceptions._logger") as mock_logger:
            bad_handler({}, self._make_context())
            mock_logger.exception.assert_called_once()
            call_kwargs = mock_logger.exception.call_args[1]
            extra = call_kwargs.get("extra", {})
            assert "traceback" in extra
            assert "TypeError" in extra["traceback"]

    def test_passes_through_on_success(self):
        """Decorator should not interfere with successful handlers."""

        @handle_unhandled_exception
        def good_handler(event, context):
            return {"statusCode": 200, "body": "ok"}

        response = good_handler({}, self._make_context())
        assert response["statusCode"] == 200

    def test_content_type_header_set(self):
        """HTTP 500 response should have Content-Type: application/json."""

        @handle_unhandled_exception
        def bad_handler(event, context):
            raise Exception("oops")

        response = bad_handler({}, self._make_context())
        assert response["headers"]["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# Amount validator tests
# ---------------------------------------------------------------------------

class TestAmountValidator:
    """Tests for validate_positive_amount."""

    def test_valid_positive_amount(self):
        assert validate_positive_amount("100.50") == Decimal("100.50")

    def test_valid_integer_amount(self):
        assert validate_positive_amount(42) == Decimal("42")

    def test_rejects_zero(self):
        with pytest.raises(ValueError, match="greater than 0"):
            validate_positive_amount(0)

    def test_rejects_negative(self):
        with pytest.raises(ValueError, match="greater than 0"):
            validate_positive_amount(-1.5)

    def test_rejects_non_numeric_string(self):
        with pytest.raises(ValueError, match="valid number"):
            validate_positive_amount("abc")

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError):
            validate_positive_amount("")

    def test_rejects_none(self):
        with pytest.raises((ValueError, Exception)):
            validate_positive_amount(None)


# ---------------------------------------------------------------------------
# Income date validator tests
# ---------------------------------------------------------------------------

class TestIncomeDateValidator:
    """Tests for validate_income_date — must not be in the future."""

    def test_valid_past_date(self):
        past = date.today() - timedelta(days=10)
        assert validate_income_date(past.isoformat()) == past

    def test_valid_today(self):
        today = date.today()
        assert validate_income_date(today.isoformat()) == today

    def test_rejects_future_date(self):
        future = date.today() + timedelta(days=1)
        with pytest.raises(ValueError, match="must not be in the future"):
            validate_income_date(future.isoformat())

    def test_rejects_far_future_date(self):
        far_future = date.today() + timedelta(days=365)
        with pytest.raises(ValueError, match="must not be in the future"):
            validate_income_date(far_future.isoformat())

    def test_rejects_invalid_string(self):
        with pytest.raises(ValueError):
            validate_income_date("not-a-date")

    def test_rejects_partial_date(self):
        with pytest.raises(ValueError):
            validate_income_date("2024-13-01")  # invalid month

    def test_accepts_date_object(self):
        today = date.today()
        assert validate_income_date(today) == today


# ---------------------------------------------------------------------------
# Goal target date validator tests
# ---------------------------------------------------------------------------

class TestGoalTargetDateValidator:
    """Tests for validate_goal_target_date — must be strictly in the future."""

    def test_valid_future_date(self):
        future = date.today() + timedelta(days=30)
        assert validate_goal_target_date(future.isoformat()) == future

    def test_rejects_today(self):
        today = date.today()
        with pytest.raises(ValueError, match="must be in the future"):
            validate_goal_target_date(today.isoformat())

    def test_rejects_past_date(self):
        past = date.today() - timedelta(days=1)
        with pytest.raises(ValueError, match="must be in the future"):
            validate_goal_target_date(past.isoformat())

    def test_rejects_invalid_string(self):
        with pytest.raises(ValueError):
            validate_goal_target_date("not-a-date")

    def test_accepts_date_object_in_future(self):
        future = date.today() + timedelta(days=10)
        assert validate_goal_target_date(future) == future


# ---------------------------------------------------------------------------
# LLM client tests
# ---------------------------------------------------------------------------

class TestLlmClient:
    """Tests for src/shared/llm — Cerebras and Bedrock routing."""

    def test_cerebras_called_when_api_key_set(self, monkeypatch):
        """call_llm uses Cerebras when CEREBRAS_API_KEY is set."""
        monkeypatch.setenv("CEREBRAS_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Transportation"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        with patch("src.shared.llm._call_cerebras", return_value="Transportation") as mock_cerebras:
            from src.shared.llm import call_llm
            result = call_llm("test prompt", max_tokens=10)

        assert result == "Transportation"
        mock_cerebras.assert_called_once()

    def test_bedrock_called_when_no_api_key(self, monkeypatch):
        """call_llm uses Bedrock when CEREBRAS_API_KEY is not set."""
        monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)

        with patch("src.shared.llm._call_bedrock", return_value="Groceries") as mock_bedrock:
            from src.shared.llm import call_llm
            result = call_llm("test prompt", max_tokens=10)

        assert result == "Groceries"
        mock_bedrock.assert_called_once()


# ---------------------------------------------------------------------------
# LLM client tests
# ---------------------------------------------------------------------------

class TestLlmClient:
    def test_cerebras_called_when_api_key_set(self, monkeypatch):
        monkeypatch.setenv("CEREBRAS_API_KEY", "test-key")
        with patch("src.shared.llm._call_cerebras", return_value="Transportation") as mock_c:
            from src.shared.llm import call_llm
            result = call_llm("test prompt", max_tokens=10)
        assert result == "Transportation"
        mock_c.assert_called_once()

    def test_bedrock_called_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
        with patch("src.shared.llm._call_bedrock", return_value="Groceries") as mock_b:
            from src.shared.llm import call_llm
            result = call_llm("test prompt", max_tokens=10)
        assert result == "Groceries"
        mock_b.assert_called_once()
