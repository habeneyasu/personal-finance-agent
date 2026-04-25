"""Expense categorizer using Cerebras / AWS Bedrock or local rule-based fallback."""
import logging
import os
import time
from decimal import Decimal

try:
    from aws_lambda_powertools import Metrics
    from aws_lambda_powertools.metrics import MetricUnit
    _metrics = Metrics(namespace="PFIP")
    _HAS_METRICS = True
except Exception:
    _HAS_METRICS = False

from src.shared.llm import call_llm

_log = logging.getLogger(__name__)

ALLOWED_CATEGORIES = [
    "Groceries",
    "Transportation",
    "Entertainment",
    "Utilities",
    "Healthcare",
    "Shopping",
    "Dining",
    "Other",
]

_PROMPT_TEMPLATE = (
    "Categorize this expense into exactly one of: Groceries, Transportation, "
    "Entertainment, Utilities, Healthcare, Shopping, Dining, Other.\n"
    "Merchant: {merchant}, Amount: {amount}\n"
    "Respond with only the category name."
)


def _local_categorize(merchant: str) -> str:
    """Simple rule-based categorization for local development."""
    m = merchant.lower()
    if any(k in m for k in ("uber", "lyft", "taxi", "bus", "metro", "transit", "train")):
        return "Transportation"
    if any(k in m for k in ("grocery", "supermarket", "whole foods", "whole", "trader joe", "safeway", "kroger", "aldi")):
        return "Groceries"
    if any(k in m for k in ("restaurant", "cafe", "pizza", "burger", "sushi", "grill", "diner", "bistro", "kitchen")):
        return "Dining"
    if any(k in m for k in ("amazon", "walmart", "target", "shop", "mall", "store", "market")):
        return "Shopping"
    if any(k in m for k in ("netflix", "spotify", "cinema", "movie", "theater", "game", "entertainment")):
        return "Entertainment"
    if any(k in m for k in ("electric", "water", "gas", "utility", "internet", "phone", "bill")):
        return "Utilities"
    if any(k in m for k in ("hospital", "clinic", "pharmacy", "doctor", "dental", "health", "medical")):
        return "Healthcare"
    return "Other"


def categorize_expense(merchant: str, amount: Decimal, user_id: str = None) -> str:
    """Categorize an expense using Cerebras/Bedrock or local rules.

    Returns a category from ALLOWED_CATEGORIES. Defaults to "Other" on any error.
    """
    environment = os.getenv("ENVIRONMENT", "").lower()

    if environment == "local" and not os.getenv("CEREBRAS_API_KEY"):
        return _local_categorize(merchant)

    prompt = _PROMPT_TEMPLATE.format(merchant=merchant, amount=amount)

    try:
        start = time.monotonic()
        category = call_llm(prompt, max_tokens=10, user_id=user_id, agent="expense_categorizer").strip()
        latency_ms = (time.monotonic() - start) * 1000

        if _HAS_METRICS:
            _metrics.add_metric(name="llm_latency_ms", unit=MetricUnit.Milliseconds, value=latency_ms)

        if not category:
            _log.error("LLM returned empty category for merchant=%s", merchant)
            return "Other"

        # Strip punctuation and take first word in case model adds explanation
        category = category.split()[0].rstrip(".,;:")

        if category not in ALLOWED_CATEGORIES:
            _log.error("LLM returned invalid category %r for merchant=%s; defaulting to Other", category, merchant)
            return "Other"

        return category

    except Exception as exc:
        _log.error("LLM categorization failed for merchant=%s: %s", merchant, exc)
        return _local_categorize(merchant)  # graceful fallback to rules
