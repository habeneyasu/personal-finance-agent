"""
Insights Agent — Validation Engine + Decision Loop.

Architecture:
    LLM Draft Answer
         ↓
    LLM Output Schema Validator (pre-gate)
    ├── Empty output          → fallback
    ├── JSON-formatted output → fallback
    └── Over MAX_ANSWER_TOKENS → fallback
         ↓
    Validation Engine (deterministic, 4 layers)
    ├── Layer 1: Numeric grounding  (±1.5% tolerance)
    ├── Layer 2: Coverage check     (categories / goals referenced)
    ├── Layer 3: Relevance check    (not a deflection, has substance)
    └── Layer 4: Consistency check  (no self-contradiction)
         ↓
    Decision Engine (explicit, bounded)
    ├── ACCEPT  → all layers pass
    ├── RETRY   → any layer fails → CoT retry (max MAX_RETRIES=1)
    │              └── re-run schema + all 4 layers on retry answer
    └── FALLBACK → retry also fails → deterministic SQL answer

Constants:
    MAX_RETRIES = 1          — hard limit on LLM retries
    MAX_ANSWER_TOKENS = 512  — reject LLM output exceeding this word count
    LLM_TIMEOUT_S = 10.0     — documented per-call timeout (Lambda-level enforcement)
    COST_LIMIT_USD = 0.01    — per-request cost guardrail
    LATENCY_LIMIT_MS = 8000  — per-request latency guardrail
"""
import json
import re
import logging
from typing import Optional

from src.insights_agent.models import OrchestrationState, ValidationResult

_log = logging.getLogger(__name__)

# ── Guardrail constants ───────────────────────────────────────────────────────
MAX_RETRIES: int = 1
MAX_ANSWER_TOKENS: int = 512
LLM_TIMEOUT_S: float = 10.0
COST_LIMIT_USD: float = 0.01
LATENCY_LIMIT_MS: float = 8000.0

# Chain-of-thought retry prompt
_COT_PROMPT = (
    "You are a precise personal finance assistant. "
    "Your previous answer contained numbers that could not be verified against the data. "
    "Think step by step:\n"
    "1. Find the exact number in the financial data that answers the question\n"
    "2. State that number explicitly\n"
    "3. Give a single clear, concise answer\n\n"
    "Financial context (JSON):\n{context_json}\n\n"
    "Question: {question}\n\n"
    "Answer (cite the exact number from the data, be concise):"
)


# ---------------------------------------------------------------------------
# LLM output schema validation (pre-gate)
# ---------------------------------------------------------------------------

def _validate_llm_output(text: str) -> tuple[bool, str]:
    """
    Strict schema validation for raw LLM output.
    Rejects structurally invalid outputs before the Validation Engine.
    Returns (valid, rejection_reason).
    """
    if not text or not text.strip():
        return False, "empty_output"
    if len(text.split()) > MAX_ANSWER_TOKENS:
        _log.warning("LLM output rejected: exceeds MAX_ANSWER_TOKENS=%d", MAX_ANSWER_TOKENS)
        return False, "output_too_long"
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return False, "output_is_json_not_prose"
    return True, "ok"


# ---------------------------------------------------------------------------
# Validation Engine — 4 deterministic layers
# ---------------------------------------------------------------------------

def _extract_numbers(text: str) -> list[float]:
    matches = re.findall(r"\$?[\d,]+\.?\d*", text)
    result = []
    for m in matches:
        try:
            result.append(float(m.replace(",", "").replace("$", "")))
        except ValueError:
            pass
    return result


def _build_context_numbers(context: dict) -> set[float]:
    nums = set()
    for key in ["total_income_90_days", "total_expenses_90_days", "net_savings_90_days",
                "expenses_this_month", "expenses_last_month", "income_this_month", "income_last_month"]:
        if key in context:
            nums.add(round(float(context[key]), 2))
    for entry in context.get("income_entries", []):
        nums.add(round(float(entry.get("amount", 0)), 2))
    for entry in context.get("expense_entries", []):
        nums.add(round(float(entry.get("amount", 0)), 2))
    for amt in context.get("expenses_by_category", {}).values():
        nums.add(round(float(amt), 2))
    for goal in context.get("savings_goals", []):
        nums.add(round(float(goal.get("target_amount", 0)), 2))
        nums.add(round(float(goal.get("current_amount", 0)), 2))
        if "progress_pct" in goal:
            nums.add(round(float(goal["progress_pct"]), 1))
    return nums


def _numbers_grounded(answer: str, context: dict) -> bool:
    """Layer 1: Every significant number in answer found in context (±1.5%)."""
    answer_nums = _extract_numbers(answer)
    if not answer_nums:
        return True
    context_nums = _build_context_numbers(context)
    for num in answer_nums:
        if num <= 1.0:
            continue
        if not any(abs(num - cn) / max(cn, 0.01) < 0.015 for cn in context_nums):
            _log.warning("Validation: number %.2f not grounded in context", num)
            return False
    return True


def _coverage_check(question: str, answer: str, context: dict) -> bool:
    """Layer 2: Answer references relevant entities (categories, goals)."""
    q = question.lower()
    answer_lower = answer.lower()
    if any(w in q for w in ["category", "categories", "spend on", "overspend"]):
        known_cats = set(context.get("expenses_by_category", {}).keys())
        if known_cats and not any(cat.lower() in answer_lower for cat in known_cats):
            _log.warning("Validation: coverage fail — no category mentioned")
            return False
    if "goal" in q and context.get("savings_goals"):
        goal_names = [g["name"].lower() for g in context["savings_goals"]]
        if not (any(name in answer_lower for name in goal_names) or "%" in answer):
            _log.warning("Validation: coverage fail — no goal referenced")
            return False
    return True


def _relevance_check(question: str, answer: str) -> bool:
    """Layer 3: Answer is not a generic deflection and has substance."""
    answer_lower = answer.lower()
    deflections = [
        "i don't have", "i do not have", "no data available",
        "cannot answer", "i'm unable to", "i am unable to", "not enough information",
    ]
    if any(d in answer_lower for d in deflections):
        _log.warning("Validation: relevance fail — deflection detected")
        return False
    if len(answer.split()) < 5:
        _log.warning("Validation: relevance fail — answer too short")
        return False
    return True


def _consistency_check(answer: str, context: dict) -> bool:
    """Layer 4: Answer does not contradict itself or the context."""
    answer_nums = _extract_numbers(answer)
    if len([n for n in answer_nums if n > 1.0]) < 2:
        return True
    answer_lower = answer.lower()
    patterns = [
        (r"(\$?[\d,]+\.?\d*)\s+(?:is\s+)?(?:higher|more|greater)\s+than\s+(?:your\s+)?(?:total\s+of\s+)?\$?([\d,]+\.?\d*)", False),
        (r"(\$?[\d,]+\.?\d*)\s+(?:is\s+)?(?:lower|less|fewer)\s+than\s+(?:your\s+)?(?:total\s+of\s+)?\$?([\d,]+\.?\d*)", True),
    ]
    for pattern, first_should_be_less in patterns:
        for m in re.findall(pattern, answer_lower):
            try:
                a = float(m[0].replace(",", "").replace("$", ""))
                b = float(m[1].replace(",", "").replace("$", ""))
                if first_should_be_less and a >= b:
                    _log.warning("Validation: consistency fail — contradiction in answer")
                    return False
                if not first_should_be_less and a <= b:
                    _log.warning("Validation: consistency fail — contradiction in answer")
                    return False
            except (ValueError, IndexError):
                pass
    return True


def _validate_answer(question: str, answer: str, context: dict) -> tuple[bool, str]:
    """Run all 4 validation layers. Returns (passed, failure_reason)."""
    if not _numbers_grounded(answer, context):
        return False, "numbers_ungrounded"
    if not _coverage_check(question, answer, context):
        return False, "coverage_insufficient"
    if not _relevance_check(question, answer):
        return False, "answer_not_relevant"
    if not _consistency_check(answer, context):
        return False, "answer_inconsistent"
    return True, "ok"


# ---------------------------------------------------------------------------
# SQL fallback — deterministic answers
# ---------------------------------------------------------------------------

def _sql_answer(question: str, context: dict) -> Optional[str]:
    """Deterministic SQL-computed answer. Returns None if not applicable."""
    q = question.lower()
    if "last month" in q and ("spend" in q or "expense" in q):
        return f"You spent ${context.get('expenses_last_month', 0):,.2f} in {context.get('last_month', 'last month')}."
    if "this month" in q and ("spend" in q or "expense" in q):
        return f"You have spent ${context.get('expenses_this_month', 0):,.2f} so far this month ({context.get('this_month', 'this month')})."
    if "biggest" in q and ("expense" in q or "category" in q or "spend" in q):
        cats = context.get("expenses_by_category", {})
        if cats:
            top = max(cats, key=lambda k: cats[k])
            return f"Your biggest expense category is {top} at ${cats[top]:,.2f}."
    if "smallest" in q and ("expense" in q or "category" in q):
        cats = context.get("expenses_by_category", {})
        if cats:
            bot = min(cats, key=lambda k: cats[k])
            return f"Your smallest expense category is {bot} at ${cats[bot]:,.2f}."
    if "total income" in q or ("how much" in q and "income" in q and "earn" in q):
        return f"Your total income over the last 90 days is ${context.get('total_income_90_days', 0):,.2f}."
    if "total expense" in q or ("how much" in q and "total" in q and "spend" in q):
        return f"Your total expenses over the last 90 days are ${context.get('total_expenses_90_days', 0):,.2f}."
    if "net saving" in q or ("balance" in q and "saving" in q):
        amt = context.get("net_savings_90_days", 0)
        sign = "saved" if amt >= 0 else "overspent by"
        return f"Your net savings over the last 90 days: you {sign} ${abs(amt):,.2f}."
    if ("on track" in q or "progress" in q) and "goal" in q:
        goals = context.get("savings_goals", [])
        if not goals:
            return "You have no savings goals set up yet."
        lines = [
            f"• {g['name']}: {g.get('progress_pct', 0):.1f}% complete — "
            f"{'on track ✓' if g.get('progress_pct', 0) >= 50 else 'behind schedule'}"
            for g in goals
        ]
        return "Savings goal progress:\n" + "\n".join(lines)
    return None


# ---------------------------------------------------------------------------
# Decision loop — explicit, bounded
# ---------------------------------------------------------------------------

def validate_and_judge(
    question: str,
    draft_answer: str,
    context: dict,
    user_id: Optional[str] = None,
    agent: str = "insights",
    state: Optional[OrchestrationState] = None,
) -> dict:
    """
    Explicit decision loop with hard retry limit (MAX_RETRIES = 1).

    Steps:
      1. Schema validation — reject structurally invalid LLM output
      2. Validation Engine (4 layers) on draft → ACCEPT or proceed to retry
      3. CoT retry (up to MAX_RETRIES) → re-run schema + 4 layers
      4. SQL fallback → deterministic answer
      5. Best-effort → return draft if no SQL answer

    Returns dict: {answer, decision, reason, retried}
    """
    from src.shared.llm import call_llm

    retries_used = 0

    # ── Step 1: Schema validation ─────────────────────────────────────────────
    schema_valid, schema_reason = _validate_llm_output(draft_answer)
    if not schema_valid:
        _log.warning("Decision: schema validation failed (%s) — going to fallback", schema_reason)
        sql = _sql_answer(question, context)
        if state:
            state.finish("fallback", f"schema_{schema_reason}")
        return {
            "answer": sql or "I was unable to answer that question. Please try rephrasing.",
            "decision": "fallback",
            "reason": f"schema_{schema_reason}",
            "retried": False,
        }

    # ── Step 2: Validation Engine on draft ───────────────────────────────────
    passed, fail_reason = _validate_answer(question, draft_answer, context)
    if state:
        state.validation_attempts.append(ValidationResult(passed=passed, failure_reason=fail_reason, attempt=1))

    if passed:
        _log.info("Decision: ACCEPT — all 4 validation layers passed on first attempt")
        if state:
            state.finish("accept", "numbers_verified")
        return {"answer": draft_answer, "decision": "accept", "reason": "numbers_verified", "retried": False}

    # ── Step 3: Retry loop (max MAX_RETRIES = 1) ─────────────────────────────
    while retries_used < MAX_RETRIES:
        retries_used += 1
        _log.warning("Decision: RETRY %d/%d — draft failed (%s)", retries_used, MAX_RETRIES, fail_reason)

        try:
            context_json = json.dumps(context, indent=2)
            cot_prompt = _COT_PROMPT.format(context_json=context_json, question=question)
            retry_answer = call_llm(cot_prompt, max_tokens=256, user_id=user_id, agent=f"{agent}_cot_retry")

            if state:
                state.llm_calls += 1
                state.retried = True

            retry_schema_valid, _ = _validate_llm_output(retry_answer)
            if not retry_schema_valid:
                _log.warning("Decision: retry output failed schema validation")
                break

            retry_passed, retry_fail = _validate_answer(question, retry_answer, context)
            if state:
                state.validation_attempts.append(
                    ValidationResult(passed=retry_passed, failure_reason=retry_fail, attempt=retries_used + 1)
                )

            if retry_passed:
                _log.info("Decision: ACCEPT retry — CoT answer passed all 4 layers")
                if state:
                    state.finish("retry", "cot_retry_verified")
                return {"answer": retry_answer, "decision": "retry", "reason": "cot_retry_verified", "retried": True}

            _log.warning("Decision: retry %d also failed (%s)", retries_used, retry_fail)

        except Exception as exc:
            _log.error("Decision: CoT retry %d raised exception: %s", retries_used, exc)
            break

    # ── Step 4: SQL fallback ──────────────────────────────────────────────────
    sql = _sql_answer(question, context)
    if sql:
        _log.info("Decision: FALLBACK — deterministic SQL answer")
        if state:
            state.finish("fallback", "sql_after_llm_unverified")
        return {"answer": sql, "decision": "fallback", "reason": "sql_after_llm_unverified", "retried": retries_used > 0}

    # ── Step 5: Best-effort ───────────────────────────────────────────────────
    _log.warning("Decision: BEST_EFFORT — no SQL answer, returning unverified draft")
    if state:
        state.finish("accept", "best_effort_unverified")
    return {"answer": draft_answer, "decision": "accept", "reason": "best_effort_unverified", "retried": retries_used > 0}
