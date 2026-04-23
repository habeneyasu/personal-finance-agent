"""Financial context builder for Insights Agent."""
from datetime import date, timedelta
from decimal import Decimal


def build_financial_context(user_id: str, conn) -> dict:
    """Build financial context for the last 90 days.

    Args:
        user_id: User ID
        conn: psycopg2 connection

    Returns:
        dict with:
            - total_income: sum of all income amounts (float)
            - total_expenses: sum of all expense amounts (float)
            - net_savings: total_income - total_expenses (float)
            - income_entries: list of {amount, source, date} dicts
            - expense_entries: list of {amount, merchant, category, date} dicts
            - expenses_by_category: dict of {category: total_amount}
            - savings_goals: list of {name, target_amount, current_amount, target_date, progress_pct} dicts
            - period: "last 90 days"
    """
    ninety_days_ago = date.today() - timedelta(days=90)

    cursor = conn.cursor()
    try:
        # Fetch income entries for last 90 days
        cursor.execute(
            """
            SELECT amount, source, date
            FROM income_entries
            WHERE user_id = %s AND date >= %s
            ORDER BY date DESC
            """,
            (user_id, ninety_days_ago),
        )
        income_rows = cursor.fetchall()

        # Fetch expense entries for last 90 days
        cursor.execute(
            """
            SELECT amount, merchant, category, date
            FROM expense_entries
            WHERE user_id = %s AND date >= %s
            ORDER BY date DESC
            """,
            (user_id, ninety_days_ago),
        )
        expense_rows = cursor.fetchall()

        # Fetch all active savings goals
        cursor.execute(
            """
            SELECT name, target_amount, current_amount, target_date
            FROM savings_goals
            WHERE user_id = %s
            """,
            (user_id,),
        )
        goal_rows = cursor.fetchall()
    finally:
        cursor.close()

    # Build income entries list
    income_entries = [
        {"amount": float(row[0]), "source": row[1], "date": str(row[2])}
        for row in income_rows
    ]

    # Build expense entries list
    expense_entries = [
        {"amount": float(row[0]), "merchant": row[1], "category": row[2], "date": str(row[3])}
        for row in expense_rows
    ]

    # Aggregate expenses by category
    expenses_by_category: dict[str, float] = {}
    for entry in expense_entries:
        cat = entry["category"]
        expenses_by_category[cat] = expenses_by_category.get(cat, 0.0) + entry["amount"]

    # Build savings goals list with progress_pct
    savings_goals = []
    for row in goal_rows:
        name, target_amount, current_amount, target_date = row
        target = float(target_amount) if target_amount else 0.0
        current = float(current_amount) if current_amount else 0.0
        progress_pct = min(100.0, (current / target * 100)) if target > 0 else 0.0
        savings_goals.append(
            {
                "name": name,
                "target_amount": target,
                "current_amount": current,
                "target_date": str(target_date),
                "progress_pct": round(progress_pct, 2),
            }
        )

    total_income = sum(e["amount"] for e in income_entries)
    total_expenses = sum(e["amount"] for e in expense_entries)
    net_savings = total_income - total_expenses

    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_savings": net_savings,
        "income_entries": income_entries,
        "expense_entries": expense_entries,
        "expenses_by_category": expenses_by_category,
        "savings_goals": savings_goals,
        "period": "last 90 days",
    }
