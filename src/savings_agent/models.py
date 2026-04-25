"""Pydantic models for the Savings Goal Agent."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

from src.shared.validation import validate_positive_amount, validate_goal_target_date


class SavingsGoalCreate(BaseModel):
    name: str
    target_amount: Decimal
    target_date: str
    initial_amount: Decimal = Decimal("0")  # existing balance at goal creation

    @field_validator("target_amount", mode="before")
    @classmethod
    def check_amount(cls, v):
        return validate_positive_amount(v)

    @field_validator("initial_amount", mode="before")
    @classmethod
    def check_initial(cls, v):
        if v is None:
            return Decimal("0")
        try:
            amt = Decimal(str(v))
        except Exception:
            raise ValueError("initial_amount must be a valid number")
        if amt < 0:
            raise ValueError("initial_amount must be >= 0")
        return amt

    @field_validator("target_date", mode="before")
    @classmethod
    def check_target_date(cls, v):
        parsed = validate_goal_target_date(v)
        return parsed.isoformat()


class SavingsGoal(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    target_amount: Decimal
    current_amount: Decimal
    initial_amount: Decimal = Decimal("0")
    target_date: date
    created_at: datetime


class SavingsGoalWithProgress(SavingsGoal):
    progress_pct: float
    predicted_completion_date: Optional[date] = None
