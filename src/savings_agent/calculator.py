"""
Savings goal progress and prediction calculations.

MVP Simplification (Known Limitation):
  current_amount = SUM(all income since goal creation) - SUM(all expenses since goal creation)
  This does not account for multiple overlapping goals or explicit per-goal contributions.
  Will be replaced with per-goal allocation tracking in a future version.
"""
from datetime import date, timedelta
from decimal import Decimal
from math import ceil
from typing import Optional


def calculate_progress(
    goal_created_at,
    income_rows: list,
    expense_rows: list,
    initial_amount: Decimal = Decimal("0"),
) -> Decimal:
    """Calculate current savings amount since goal creation.

    Formula: initial_amount + SUM(income since creation) - SUM(expenses since creation)

    The initial_amount accounts for any existing balance the user had when
    the goal was created (defaults to 0 for backward compatibility).
    """
    total_income = sum(Decimal(str(row[0])) for row in income_rows) if income_rows else Decimal("0")
    total_expenses = sum(Decimal(str(row[0])) for row in expense_rows) if expense_rows else Decimal("0")
    return initial_amount + total_income - total_expenses


def predict_completion(
    current_amount: Decimal,
    target_amount: Decimal,
    monthly_rate: Decimal,
) -> Optional[date]:
    """Predict the date when the savings goal will be reached.

    Args:
        current_amount: current saved amount
        target_amount: goal target amount
        monthly_rate: average net savings per month (last 30 days)

    Returns:
        predicted completion date, or None if rate <= 0
    """
    if monthly_rate <= 0:
        return None

    remaining = target_amount - current_amount
    if remaining <= 0:
        return date.today()

    days_needed = ceil(float(remaining) / float(monthly_rate / 30))
    return date.today() + timedelta(days=days_needed)


def calculate_monthly_rate(income_rows: list, expense_rows: list) -> Decimal:
    """Calculate net savings over the last 30 days.

    Args:
        income_rows: list of (amount, date) tuples
        expense_rows: list of (amount, date) tuples

    Returns:
        net savings for the last 30 days as Decimal (the monthly rate)
    """
    today = date.today()
    cutoff = today - timedelta(days=30)

    income_30 = sum(
        Decimal(str(row[0]))
        for row in income_rows
        if row[1] >= cutoff
    ) if income_rows else Decimal("0")

    expenses_30 = sum(
        Decimal(str(row[0]))
        for row in expense_rows
        if row[1] >= cutoff
    ) if expense_rows else Decimal("0")

    return income_30 - expenses_30
