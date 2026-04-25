"""
Pydantic models for the Insights Agent.

Includes:
  - Agent contracts (typed I/O for each worker)
  - OrchestrationState (tracks full execution flow)
  - InsightQuery / InsightResponse (API boundary)
"""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Agent worker contracts — strict typed outputs
# ---------------------------------------------------------------------------

class IncomeEntry(BaseModel):
    amount: float
    source: str
    date: str


class IncomeAgentContract(BaseModel):
    """Typed output contract for Income_Agent worker."""
    agent: Literal["income_agent"] = "income_agent"
    total_income_90_days: float
    income_this_month: float
    income_last_month: float
    entries: list[IncomeEntry]
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class ExpenseEntry(BaseModel):
    amount: float
    merchant: str
    category: str
    date: str


class ExpenseAgentContract(BaseModel):
    """Typed output contract for Expense_Agent worker."""
    agent: Literal["expense_agent"] = "expense_agent"
    total_expenses_90_days: float
    expenses_this_month: float
    expenses_last_month: float
    by_category: dict[str, float]
    entries: list[ExpenseEntry]
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class SavingsGoalEntry(BaseModel):
    name: str
    target_amount: float
    current_amount: float
    target_date: str
    progress_pct: float


class SavingsAgentContract(BaseModel):
    """Typed output contract for Savings_Goal_Agent worker."""
    agent: Literal["savings_agent"] = "savings_agent"
    goals: list[SavingsGoalEntry]
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Orchestration state — tracks full execution flow
# ---------------------------------------------------------------------------

class ValidationResult(BaseModel):
    passed: bool
    failure_reason: Optional[str] = None  # numbers_ungrounded / coverage_insufficient / etc.
    attempt: int  # 1 = first draft, 2 = CoT retry


class OrchestrationState(BaseModel):
    """
    Tracks the full execution flow of a single insights query.
    Persisted in logs; can be stored in DB for observability.
    """
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    question: str
    started_at: datetime = Field(default_factory=datetime.utcnow)

    # Worker agent results
    data_sources: list[str] = Field(default_factory=list)
    income_fetched: bool = False
    expense_fetched: bool = False
    savings_fetched: bool = False

    # LLM calls
    llm_calls: int = 0
    llm_total_latency_ms: float = 0.0
    llm_estimated_cost_usd: float = 0.0

    # Validation results per attempt
    validation_attempts: list[ValidationResult] = Field(default_factory=list)

    # Final decision
    decision: Optional[Literal["accept", "retry", "fallback", "sql_local"]] = None
    reason: Optional[str] = None
    retried: bool = False

    # Guardrail flags
    cost_limit_exceeded: bool = False
    latency_limit_exceeded: bool = False

    completed_at: Optional[datetime] = None

    def finish(self, decision: str, reason: str) -> None:
        self.decision = decision  # type: ignore[assignment]
        self.reason = reason
        self.completed_at = datetime.utcnow()

    def total_latency_ms(self) -> float:
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return 0.0


# ---------------------------------------------------------------------------
# API boundary models
# ---------------------------------------------------------------------------

class InsightQuery(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def question_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question must not be empty")
        return v.strip()


class InsightResponse(BaseModel):
    answer: str
    query: str
    generated_at: datetime
    trace_id: Optional[str] = None
    decision: Optional[str] = None   # accept / retry / fallback / sql_local
    reason: Optional[str] = None
    retried: Optional[bool] = None
    data_sources: Optional[list[str]] = None
