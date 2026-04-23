"""Pydantic models for the Expense Agent."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator

from src.shared.validation import validate_positive_amount, validate_income_date


class ExpenseEntryCreate(BaseModel):
    amount: Decimal
    merchant: str
    date: str

    @field_validator("amount", mode="before")
    @classmethod
    def check_amount(cls, v):
        return validate_positive_amount(v)

    @field_validator("date", mode="before")
    @classmethod
    def check_date(cls, v):
        parsed = validate_income_date(v)
        return parsed.isoformat()


class ExpenseEntry(BaseModel):
    id: UUID
    user_id: UUID
    amount: Decimal
    merchant: str
    category: str
    date: date
    created_at: datetime
