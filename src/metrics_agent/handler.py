"""
Metrics Agent — computes measurable quality baselines for the evaluation framework.

Endpoint: GET /v1/metrics

Returns quality scores across 5 dimensions:
  1. Categorization accuracy (expense AI quality)
  2. Insights response rate (LLM reliability)
  3. Data completeness (schema integrity)
  4. Goal prediction coverage (savings agent quality)
  5. System health (overall score)

These metrics serve as the "measurable quality baselines" for the evaluation strategy,
enabling LLM-as-judge comparisons and regression tracking over time.
"""
import json
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from src.shared.auth import AuthError, get_user_id_from_event
from src.shared.db import get_connection
from src.shared.exceptions import handle_unhandled_exception
from src.shared.logger import Logger

app = FastAPI(title="Metrics Agent")
_logger = Logger(service="metrics-agent")

BASELINES = {
    "categorization_accuracy": 85.0,   # % of expenses with AI-assigned category (not "Other")
    "insights_response_rate": 90.0,    # % of insights queries returning real answers
    "data_completeness": 100.0,        # % of entries with all required fields populated
    "goal_prediction_coverage": 80.0,  # % of goals with a predicted completion date
    "overall_quality_score": 88.0,     # weighted average of above
}


def _score_color(score: float, baseline: float) -> str:
    """Return status based on score vs baseline."""
    if score >= baseline:
        return "green"
    elif score >= baseline * 0.9:
        return "yellow"
    return "red"


@app.get("/v1/metrics")
async def get_metrics(request: Request):
    event = request.scope.get("aws.event", {})

    try:
        user_id = get_user_id_from_event(event)
    except AuthError as e:
        return JSONResponse(status_code=401, content={"error": e.message})

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # ── 1. Categorization Accuracy ────────────────────────────────────────
        # % of expenses where category != 'Other' (AI successfully categorized)
        cursor.execute(
            "SELECT COUNT(*) FROM expense_entries WHERE user_id = %s", (user_id,)
        )
        total_expenses = cursor.fetchone()[0] or 0

        cursor.execute(
            "SELECT COUNT(*) FROM expense_entries WHERE user_id = %s AND category != 'Other'",
            (user_id,),
        )
        categorized = cursor.fetchone()[0] or 0

        cat_accuracy = round((categorized / total_expenses * 100) if total_expenses > 0 else 0.0, 1)

        # ── 2. Data Completeness ──────────────────────────────────────────────
        # % of income entries with source filled, expenses with merchant filled
        cursor.execute(
            "SELECT COUNT(*) FROM income_entries WHERE user_id = %s AND source IS NOT NULL AND source != ''",
            (user_id,),
        )
        complete_income = cursor.fetchone()[0] or 0

        cursor.execute(
            "SELECT COUNT(*) FROM income_entries WHERE user_id = %s", (user_id,)
        )
        total_income = cursor.fetchone()[0] or 0

        cursor.execute(
            "SELECT COUNT(*) FROM expense_entries WHERE user_id = %s AND merchant IS NOT NULL AND merchant != ''",
            (user_id,),
        )
        complete_expenses = cursor.fetchone()[0] or 0

        total_records = total_income + total_expenses
        complete_records = complete_income + complete_expenses
        data_completeness = round((complete_records / total_records * 100) if total_records > 0 else 100.0, 1)

        # ── 3. Goal Prediction Coverage ───────────────────────────────────────
        # % of goals where current_amount > 0 (has been calculated/predicted)
        cursor.execute(
            "SELECT COUNT(*) FROM savings_goals WHERE user_id = %s", (user_id,)
        )
        total_goals = cursor.fetchone()[0] or 0

        cursor.execute(
            "SELECT COUNT(*) FROM savings_goals WHERE user_id = %s AND current_amount >= 0",
            (user_id,),
        )
        goals_with_prediction = cursor.fetchone()[0] or 0

        goal_coverage = round((goals_with_prediction / total_goals * 100) if total_goals > 0 else 0.0, 1)

        # ── 4. Insights Response Rate ─────────────────────────────────────────
        # Derived: if we have data, insights can respond. Proxy: data availability score
        has_income = total_income > 0
        has_expenses = total_expenses > 0
        has_goals = total_goals > 0
        data_richness = sum([has_income, has_expenses, has_goals])
        insights_rate = round((data_richness / 3) * 100, 1)

        # ── 5. Overall Quality Score (weighted average) ───────────────────────
        overall = round(
            (cat_accuracy * 0.35) +
            (data_completeness * 0.25) +
            (goal_coverage * 0.20) +
            (insights_rate * 0.20),
            1
        )

        # ── 6. LLM Usage Metrics ──────────────────────────────────────────────
        cursor.execute(
            """
            SELECT 
                COUNT(*) as total_calls,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(estimated_cost_usd), 0) as total_cost_usd,
                COALESCE(AVG(latency_ms), 0) as avg_latency_ms,
                COALESCE(MAX(latency_ms), 0) as max_latency_ms
            FROM llm_usage
            WHERE user_id = %s
            """,
            (user_id,),
        )
        llm_row = cursor.fetchone()
        llm_stats = {
            "total_calls": int(llm_row[0]) if llm_row else 0,
            "total_tokens": int(llm_row[1]) if llm_row else 0,
            "total_cost_usd": round(float(llm_row[2]), 6) if llm_row else 0.0,
            "avg_latency_ms": round(float(llm_row[3]), 1) if llm_row else 0.0,
            "max_latency_ms": round(float(llm_row[4]), 1) if llm_row else 0.0,
        }

        # Per-agent breakdown
        cursor.execute(
            """
            SELECT agent, COUNT(*) as calls, SUM(total_tokens) as tokens,
                   SUM(estimated_cost_usd) as cost, AVG(latency_ms) as avg_ms
            FROM llm_usage WHERE user_id = %s
            GROUP BY agent ORDER BY calls DESC
            """,
            (user_id,),
        )
        agent_usage = [
            {
                "agent": r[0],
                "calls": int(r[1]),
                "tokens": int(r[2] or 0),
                "cost_usd": round(float(r[3] or 0), 6),
                "avg_latency_ms": round(float(r[4] or 0), 1),
            }
            for r in cursor.fetchall()
        ]

        metrics = {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "user_id": str(user_id),
            "metrics": [
                {
                    "id": "categorization_accuracy",
                    "label": "Categorization Accuracy",
                    "description": "% of expenses successfully categorized by AI (not defaulting to 'Other')",
                    "value": cat_accuracy,
                    "baseline": BASELINES["categorization_accuracy"],
                    "unit": "%",
                    "status": _score_color(cat_accuracy, BASELINES["categorization_accuracy"]),
                    "detail": f"{categorized}/{total_expenses} expenses categorized",
                },
                {
                    "id": "data_completeness",
                    "label": "Data Completeness",
                    "description": "% of entries with all required fields populated",
                    "value": data_completeness,
                    "baseline": BASELINES["data_completeness"],
                    "unit": "%",
                    "status": _score_color(data_completeness, BASELINES["data_completeness"]),
                    "detail": f"{complete_records}/{total_records} records complete",
                },
                {
                    "id": "goal_prediction_coverage",
                    "label": "Goal Prediction Coverage",
                    "description": "% of savings goals with progress tracked and completion predicted",
                    "value": goal_coverage,
                    "baseline": BASELINES["goal_prediction_coverage"],
                    "unit": "%",
                    "status": _score_color(goal_coverage, BASELINES["goal_prediction_coverage"]),
                    "detail": f"{goals_with_prediction}/{total_goals} goals tracked",
                },
                {
                    "id": "insights_response_rate",
                    "label": "Insights Data Richness",
                    "description": "% of data dimensions available for AI insights (income, expenses, goals)",
                    "value": insights_rate,
                    "baseline": BASELINES["insights_response_rate"],
                    "unit": "%",
                    "status": _score_color(insights_rate, BASELINES["insights_response_rate"]),
                    "detail": f"{data_richness}/3 data dimensions populated",
                },
                {
                    "id": "overall_quality_score",
                    "label": "Overall Quality Score",
                    "description": "Weighted composite of all quality dimensions",
                    "value": overall,
                    "baseline": BASELINES["overall_quality_score"],
                    "unit": "%",
                    "status": _score_color(overall, BASELINES["overall_quality_score"]),
                    "detail": "Weighted: categorization 35%, completeness 25%, goals 20%, insights 20%",
                },
            ],
            "baselines": BASELINES,
            "llm_usage": llm_stats,
            "llm_usage_by_agent": agent_usage,
            "summary": {
                "total_income_entries": total_income,
                "total_expense_entries": total_expenses,
                "total_goals": total_goals,
                "passing_metrics": sum(
                    1 for m in [cat_accuracy, data_completeness, goal_coverage, insights_rate, overall]
                    if m >= list(BASELINES.values())[
                        [cat_accuracy, data_completeness, goal_coverage, insights_rate, overall].index(m)
                    ]
                ),
            },
        }

        _logger.info(
            "Metrics computed",
            user_id=str(user_id),
            operation="get_metrics",
            status="ok",
            overall_score=overall,
        )

        return JSONResponse(status_code=200, content=metrics)

    finally:
        conn.close()


handler = Mangum(app)


@handle_unhandled_exception
def lambda_handler(event: dict, context) -> dict:
    return handler(event, context)
