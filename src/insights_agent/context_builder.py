"""
Financial context builder for Insights Agent.

Implements the Coordinator–Worker pattern with typed Pydantic contracts:
  Insights_Agent (Coordinator)
      ├── fetch_income_context()    → IncomeAgentContract
      ├── fetch_expense_context()   → ExpenseAgentContract
      └── fetch_savings_context()   → SavingsAgentContract

Each worker returns a validated Pydantic model. The coordinator merges them
into a single context dict for the LLM and Validation Engine, and updates
the OrchestrationState with data freshness and source tracking.

In production, these would be HTTP calls to the respective Lambda endpoints.
In the current deployment, they share the same DB connection for efficiency,
but the contract boundaries are strictly enforced via Pydantic validation.
"""
from datetime import date, timedelta

from src.insights_agent.models import (
    ExpenseAgentContract,
    ExpenseEntry,
    IncomeAgentContract,
    IncomeEntry,
    OrchestrationState,
    SavingsAgentContract,
    SavingsGoalEntry,
)


# ---------------------------------------------------------------------------
# Worker agents — return typed Pydantic contracts
# ---------------------------------------------------------------------------

def fetch_income_context(user_id: str, conn) -> IncomeAgentContract:
    """Income_Agent worker — returns validated IncomeAgentContract."""
    ninety_days_ago = date.today() - timedelta(days=90)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT amount, source, date FROM income_entries "
            "WHERE user_id = %s AND date >= %s ORDER BY date DESC",
            (user_id, ninety_days_ago),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()

    entries = [IncomeEntry(amount=float(r[0]), source=r[1], date=str(r[2])) for r in rows]

    today = date.today()
    this_month = f"{today.year}-{str(today.month).zfill(2)}"
    last_month = (
        f"{today.year - 1}-12" if today.month == 1
        else f"{today.year}-{str(today.month - 1).zfill(2)}"
    )

    def _month(d: str) -> str:
        return d[:7]

    return IncomeAgentContract(
        total_income_90_days=sum(e.amount for e in entries),
        income_this_month=sum(e.amount for e in entries if _month(e.date) == this_month),
        income_last_month=sum(e.amount for e in entries if _month(e.date) == last_month),
        entries=entries,
    )


def fetch_expense_context(user_id: str, conn) -> ExpenseAgentContract:
    """Expense_Agent worker — returns validated ExpenseAgentContract."""
    ninety_days_ago = date.today() - timedelta(days=90)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT amount, merchant, category, date FROM expense_entries "
            "WHERE user_id = %s AND date >= %s ORDER BY date DESC",
            (user_id, ninety_days_ago),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()

    entries = [
        ExpenseEntry(amount=float(r[0]), merchant=r[1], category=r[2], date=str(r[3]))
        for r in rows
    ]

    today = date.today()
    this_month = f"{today.year}-{str(today.month).zfill(2)}"
    last_month = (
        f"{today.year - 1}-12" if today.month == 1
        else f"{today.year}-{str(today.month - 1).zfill(2)}"
    )

    def _month(d: str) -> str:
        return d[:7]

    by_category: dict[str, float] = {}
    for e in entries:
        by_category[e.category] = by_category.get(e.category, 0.0) + e.amount

    return ExpenseAgentContract(
        total_expenses_90_days=sum(e.amount for e in entries),
        expenses_this_month=sum(e.amount for e in entries if _month(e.date) == this_month),
        expenses_last_month=sum(e.amount for e in entries if _month(e.date) == last_month),
        by_category=by_category,
        entries=entries,
    )


def fetch_savings_context(user_id: str, conn) -> SavingsAgentContract:
    """Savings_Goal_Agent worker — returns validated SavingsAgentContract."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT name, target_amount, current_amount, target_date FROM savings_goals "
            "WHERE user_id = %s",
            (user_id,),
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()

    goals = []
    for row in rows:
        name, target, current, target_date = row
        target_f = float(target) if target else 0.0
        current_f = float(current) if current else 0.0
        progress_pct = min(100.0, current_f / target_f * 100) if target_f > 0 else 0.0
        goals.append(SavingsGoalEntry(
            name=name,
            target_amount=target_f,
            current_amount=current_f,
            target_date=str(target_date),
            progress_pct=round(progress_pct, 2),
        ))

    return SavingsAgentContract(goals=goals)


# ---------------------------------------------------------------------------
# Coordinator — merges typed contracts into unified LLM context
# ---------------------------------------------------------------------------

def build_financial_context(
    user_id: str,
    conn,
    state: OrchestrationState | None = None,
) -> dict:
    """
    Coordinator: invokes each worker agent, validates their typed contracts,
    and merges outputs into a unified context dict for the LLM.

    Updates OrchestrationState with data_sources and freshness if provided.
    """
    today = date.today()
    this_month = f"{today.year}-{str(today.month).zfill(2)}"
    last_month = (
        f"{today.year - 1}-12" if today.month == 1
        else f"{today.year}-{str(today.month - 1).zfill(2)}"
    )

    # ── Invoke each worker — Pydantic validates the contract on return ────────
    income: IncomeAgentContract = fetch_income_context(user_id, conn)
    expense: ExpenseAgentContract = fetch_expense_context(user_id, conn)
    savings: SavingsAgentContract = fetch_savings_context(user_id, conn)

    # ── Track data sources and freshness ─────────────────────────────────────
    data_sources: list[str] = []
    if income.entries:
        data_sources.append("income_agent")
    if expense.entries:
        data_sources.append("expense_agent")
    if savings.goals:
        data_sources.append("savings_agent")

    if state is not None:
        state.data_sources = data_sources
        state.income_fetched = bool(income.entries)
        state.expense_fetched = bool(expense.entries)
        state.savings_fetched = bool(savings.goals)

    net_savings = income.total_income_90_days - expense.total_expenses_90_days

    # ── Merge into unified context dict (LLM-friendly flat structure) ─────────
    return {
        "today": str(today),
        "this_month": this_month,
        "last_month": last_month,
        "period": "last 90 days",
        # Income
        "total_income_90_days": income.total_income_90_days,
        "income_this_month": round(income.income_this_month, 2),
        "income_last_month": round(income.income_last_month, 2),
        "income_entries": [e.model_dump() for e in income.entries],
        # Expense
        "total_expenses_90_days": expense.total_expenses_90_days,
        "expenses_this_month": round(expense.expenses_this_month, 2),
        "expenses_last_month": round(expense.expenses_last_month, 2),
        "expenses_by_category": expense.by_category,
        "expense_entries": [e.model_dump() for e in expense.entries],
        # Savings
        "savings_goals": [g.model_dump() for g in savings.goals],
        # Derived
        "net_savings_90_days": net_savings,
        # Traceability
        "data_sources": data_sources,
        # Freshness — ISO timestamps from each worker contract
        "data_freshness": {
            "income_agent": income.fetched_at.isoformat(),
            "expense_agent": expense.fetched_at.isoformat(),
            "savings_agent": savings.fetched_at.isoformat(),
        },
    }
