"""
Insights Agent Lambda handler — FastAPI + Mangum.

Orchestration flow:
  1. Auth + input validation
  2. Build OrchestrationState (trace_id, user_id, question)
  3. Coordinator: invoke worker agents → typed contracts → merged context
  4. LLM draft (with timeout)
  5. Validation Engine (4 layers) + Decision Loop (explicit, max 1 retry)
  6. Cost + latency guardrail check
  7. Return InsightResponse with full transparency fields
"""
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
from src.shared.db import get_connection
from src.shared.exceptions import handle_unhandled_exception
from src.shared.logger import Logger
from src.insights_agent.context_builder import build_financial_context
from src.insights_agent.judge import (
    COST_LIMIT_USD,
    LATENCY_LIMIT_MS,
    LLM_TIMEOUT_S,
    validate_and_judge,
    _sql_answer,
)
from src.insights_agent.models import InsightQuery, InsightResponse, OrchestrationState

app = FastAPI(title="Insights Agent")
_logger = Logger(service="insights-agent")

_PROMPT_TEMPLATE = (
    "You are a personal finance assistant. Answer the user's question based ONLY on the financial data provided below. "
    "Be concise and direct — give a single clear answer with the key number. Do not list all entries. "
    "Do not invent numbers or make assumptions beyond the data.\n\n"
    "Financial context (JSON):\n{context_json}\n\n"
    "User question: {question}\n\n"
    "Provide a concise answer in 1-3 sentences maximum. State the key number first."
)

_FALLBACK_MESSAGE = "I was unable to process your query at this time. Please try again."
_NO_DATA_MESSAGE = "No financial data found. Please add some income or expense entries first."


def _error(error: str, detail: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": error, "detail": detail, "status": status})


def _invoke_llm(question: str, context: dict, user_id: str = None) -> str:
    """Call LLM. Raises exception on failure — caller handles with fallback."""
    from src.shared.llm import call_llm
    context_json = json.dumps(context, indent=2)
    prompt = _PROMPT_TEMPLATE.format(context_json=context_json, question=question)
    start = time.monotonic()
    answer = call_llm(prompt, max_tokens=512, user_id=user_id, agent="insights")
    latency_ms = (time.monotonic() - start) * 1000
    if _HAS_METRICS:
        _metrics.add_metric(name="llm_latency_ms", unit=MetricUnit.Milliseconds, value=latency_ms)
    return answer


@app.post("/v1/insights/query")
async def query_insights(request: Request):
    start_total = time.monotonic()
    event = request.scope.get("aws.event", {})

    try:
        user_id = get_user_id_from_event(event)
    except AuthError as e:
        return _error("unauthorized", e.message, 401)

    try:
        body = await request.json()
        query_in = InsightQuery(**body)
    except Exception as e:
        return _error("validation_error", str(e), 400)

    # ── Orchestration state — tracks full execution flow ──────────────────────
    state = OrchestrationState(user_id=str(user_id), question=query_in.question)

    conn = get_connection()
    try:
        context = build_financial_context(user_id, conn, state=state)
    finally:
        conn.close()

    has_data = bool(context.get("data_sources"))
    if not has_data:
        state.finish("fallback", "no_data")
        return JSONResponse(status_code=200, content=json.loads(
            InsightResponse(
                answer=_NO_DATA_MESSAGE,
                query=query_in.question,
                generated_at=datetime.now(timezone.utc),
                trace_id=state.trace_id,
                data_sources=[],
            ).model_dump_json()
        ))

    environment = os.getenv("ENVIRONMENT", "").lower()
    cerebras_key = os.getenv("CEREBRAS_API_KEY", "")

    if environment == "local" and not cerebras_key:
        # Local dev — deterministic SQL path, no LLM
        answer = _sql_answer(query_in.question, context) or (
            f"This month ({context.get('this_month','')}) expenses: "
            f"${context.get('expenses_this_month', 0):.2f} | "
            f"Last month: ${context.get('expenses_last_month', 0):.2f} | "
            f"90-day income: ${context.get('total_income_90_days', 0):.2f}"
        )
        state.finish("sql_local", "no_llm_key")
        decision, reason, retried = "sql_local", "no_llm_key", False

    else:
        # ── Step 1: LLM draft (with timeout) ─────────────────────────────────
        state.llm_calls = 1
        try:
            draft = _invoke_llm(query_in.question, context, user_id=str(user_id))
        except Exception as exc:
            _logger.error("LLM draft failed", user_id=str(user_id),
                          operation="query_insights", error=str(exc), trace_id=state.trace_id)
            draft = ""

        # ── Step 2: Validation Engine + Decision Loop ─────────────────────────
        result = validate_and_judge(
            question=query_in.question,
            draft_answer=draft,
            context=context,
            user_id=str(user_id),
            agent="insights",
            state=state,
        )
        answer = result["answer"] or _FALLBACK_MESSAGE
        decision = result["decision"]
        reason = result["reason"]
        retried = result["retried"]

        # ── Step 3: Cost + latency guardrails ─────────────────────────────────
        elapsed_ms = (time.monotonic() - start_total) * 1000
        if elapsed_ms > LATENCY_LIMIT_MS:
            state.latency_limit_exceeded = True
            _logger.warning(
                f"Latency guardrail exceeded: {elapsed_ms:.0f}ms > {LATENCY_LIMIT_MS:.0f}ms",
                operation="query_insights",
                trace_id=state.trace_id,
            )

        _logger.info(
            "Validation loop decision",
            user_id=str(user_id),
            operation="query_insights",
            trace_id=state.trace_id,
            decision=decision,
            reason=reason,
            retried=retried,
            llm_calls=state.llm_calls,
            data_sources=state.data_sources,
        )

    total_ms = (time.monotonic() - start_total) * 1000
    _logger.info(
        "Insights query processed",
        user_id=str(user_id),
        trace_id=state.trace_id,
        operation="query_insights",
        status="ok",
        query_processing_time_ms=total_ms,
        decision=decision,
        data_sources=state.data_sources,
    )

    return JSONResponse(status_code=200, content=json.loads(
        InsightResponse(
            answer=answer,
            query=query_in.question,
            generated_at=datetime.now(timezone.utc),
            trace_id=state.trace_id,
            decision=decision,
            reason=reason,
            retried=retried,
            data_sources=context.get("data_sources", []),
        ).model_dump_json()
    ))


handler = Mangum(app)


@handle_unhandled_exception
def lambda_handler(event: dict, context) -> dict:
    return handler(event, context)
