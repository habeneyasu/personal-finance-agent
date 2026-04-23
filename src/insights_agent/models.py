"""Pydantic models for the Insights Agent."""
from datetime import datetime

from pydantic import BaseModel, field_validator


class InsightQuery(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def question_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question must not be empty")
        return v


class InsightResponse(BaseModel):
    answer: str
    query: str
    generated_at: datetime
