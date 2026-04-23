"""Insights Agent Lambda handler — FastAPI + Mangum."""
import json
import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

try:
    from aws_lambda_powertools import Metrics
    from aws_lambda_powertools.metrics import MetricUnit

    _metrics = Metrics(namespace="PFIP")
    _HAS_METRICS = True
except Exception:
    _HAS_METRICS = False

from src.shared.auth import AuthError, get_user_id_from_event
from src.shared.db import get_connection, get_cursor
from src.shared.exceptions import handle_unhandled_exception
from src.shared.logger import Logger
from src.insights_agent.context_builder import build_financial_context
from src.insights_agent.models import InsightQuery, InsightResponse

app = FastAPI(title="Insights Agent")
_logger = Logger(service="insights-agent")

_PROMPT_TEMPLATE = (
    "You are a personal finance assistant. Answer the user's question based ONLY on the "
    "financial data provided below. Do not invent numbers or make assumptions beyond the data.\n\n"
    "Financial context (JSON):\n{context_json}\n\n"
    "User question: {question}\n\n"
    "Provide a concise, helpful answer. If the data is insufficient to answer, say so clearly."
)

_FALLBACK_MESSAGE = "I was unable to process your query at this time. Please try again."
_NO_DATA_MESSAGE = (
    "No financial data found. Please add some income or expense entries first."
)


def _error(error: str, detail: str, status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": error, "detail": detail, "status": status},
    )


def _invoke_llm(question: str, context: dict) -> str:
    """Call LLM (Cerebras or Bedrock) and return the answer string."""
    from src.shared.llm import call_llm
    context_json = json.dumps(context, indent=2)
    prompt = _PROMPT_TEMPLATE.format(context_json=context_json, question=question)
    start = time.monotonic()
    answer = call_llm(prompt, max_tokens=512)
    latency_ms = (time.monotonic() - start) * 1000
    if _HAS_METRICS:
        _metrics.add_metric(name="llm_latency_ms", unit=MetricUnit.Milliseconds, value=latency_ms)
    return answer


@app.post("/v1/insights/query")
async def query_insights(request: Request):
    start_total = time.monotonic()
    event = request.scope.get("aws.event", {})

    # Auth
    try:
        user_id = get_user_id_from_event(event)
    except AuthError as e:
        return _error("unauthorized", e.message, 401)

    # Parse + validate body
    try:
        body = await request.json()
        query_in = InsightQuery(**body)
    except Exception as e:
        return _error("validation_error", str(e), 400)

    # Build financial context
    conn = get_connection()
    try:
        context = build_financial_context(user_id, conn)
    finally:
        conn.close()

    # Check if there is any data at all
    has_data = (
        len(context["income_entries"]) > 0
        or len(context["expense_entries"]) > 0
        or len(context["savings_goals"]) > 0
    )
    if not has_data:
        _logger.info(
            "No financial data for insights query",
            user_id=str(user_id),
            operation="query_insights",
            status="ok",
        )
        return JSONResponse(
            status_code=200,
            content=json.loads(
                InsightResponse(
                    answer=_NO_DATA_MESSAGE,
                    query=query_in.question,
                    generated_at=datetime.now(timezone.utc),
                ).model_dump_json()
            ),
        )

    environment = os.getenv("ENVIRONMENT", "").lower()
    cerebras_key = os.getenv("CEREBRAS_API_KEY", "")

    # Local dev without API key: return rule-based summary
    if environment == "local" and not cerebras_key:
        answer = (
            f"Based on your data: total income ${context['total_income']:.2f}, "
            f"total expenses ${context['total_expenses']:.2f}, "
            f"net savings ${context['net_savings']:.2f}."
        )
    else:
        # Invoke LLM (Cerebras if key set, else Bedrock)
        try:
            answer = _invoke_llm(query_in.question, context)
            if not answer:
                answer = _FALLBACK_MESSAGE
        except Exception as exc:
            _logger.error(
                "LLM invocation failed",
                user_id=str(user_id),
                operation="query_insights",
                status="error",
                error=str(exc),
            )
            answer = _FALLBACK_MESSAGE

    total_ms = (time.monotonic() - start_total) * 1000
    _logger.info(
        "Insights query processed",
        user_id=str(user_id),
        operation="query_insights",
        status="ok",
        query_processing_time=total_ms,
    )

    return JSONResponse(
        status_code=200,
        content=json.loads(
            InsightResponse(
                answer=answer,
                query=query_in.question,
                generated_at=datetime.now(timezone.utc),
            ).model_dump_json()
        ),
    )


# Mangum adapter wraps the FastAPI app for Lambda
handler = Mangum(app)


@handle_unhandled_exception
def lambda_handler(event: dict, context) -> dict:
    return handler(event, context)
