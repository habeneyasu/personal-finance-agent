"""Pydantic models for the Income Agent."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

from src.shared.validation import validate_positive_amount, validate_income_date


class IncomeEntryCreate(BaseModel):
    amount: Decimal
    source: str
    date: str
    notes: Optional[str] = None

    @field_validator("amount", mode="before")
    @classmethod
    def check_amount(cls, v):
        return validate_positive_amount(v)

    @field_validator("date", mode="before")
    @classmethod
    def check_date(cls, v):
        parsed = validate_income_date(v)
        return parsed.isoformat()


class IncomeEntry(BaseModel):
    id: UUID
    user_id: UUID
    amount: Decimal
    source: str
    date: date
    notes: Optional[str] = None
    created_at: datetime
