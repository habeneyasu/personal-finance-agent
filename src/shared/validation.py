"""Shared Pydantic validators for PFIP agents."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import field_validator


def validate_positive_amount(value: Any) -> Decimal:
    """Validate that amount is a positive decimal (> 0)."""
    try:
        amount = Decimal(str(value))
    except Exception:
        raise ValueError("amount must be a valid number")
    if amount <= 0:
        raise ValueError("amount must be greater than 0")
    return amount


def validate_iso_date(value: Any) -> date:
    """Validate that a value is a valid ISO 8601 date string or date object."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValueError(f"date must be a valid ISO 8601 date string, got: {value!r}")
    raise ValueError(f"date must be a string or date, got: {type(value).__name__}")


def validate_income_date(value: Any) -> date:
    """Validate ISO 8601 date that is not in the future."""
    parsed = validate_iso_date(value)
    if parsed > date.today():
        raise ValueError("income date must not be in the future")
    return parsed


def validate_goal_target_date(value: Any) -> date:
    """Validate ISO 8601 date that is strictly in the future."""
    parsed = validate_iso_date(value)
    if parsed <= date.today():
        raise ValueError("goal target date must be in the future")
    return parsed
